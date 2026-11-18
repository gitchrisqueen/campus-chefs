from decimal import Decimal

from django import forms
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.html import escape

from bookings.models import Booking

from .models import ALLERGENS, DIETARY_TAGS, CookProfile, MealType, MenuItem, Offering, OfferingNeed
from .money import format_cents, suggested_share_cents

NO_PROFIT = "Diners together can't pay more than the groceries cost."
DATETIME_LOCAL = "%Y-%m-%dT%H:%M"
MAX_BRING_ITEMS = 10


def _dollars(cents: int) -> Decimal:
    return Decimal(cents).scaleb(-2)


def _cents(dollars: Decimal) -> int:
    return int(dollars * 100)


class CookBioForm(forms.ModelForm):
    class Meta:
        model = CookProfile
        fields = ["bio"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 3})}
        labels = {"bio": "About your cooking"}
        help_texts = {"bio": "Shown on your public cook page. Up to 500 characters."}


class CookSetupForm(CookBioForm):
    food_safety = forms.BooleanField(
        label="I will cook in a clean kitchen and declare every allergen in my dishes",
        error_messages={"required": "Cooks must accept the food-safety acknowledgement."},
    )


class MenuItemForm(forms.ModelForm):
    """A dish. The cook must confirm the allergen list every time they save it (plan 1.2, MENU-02)."""

    allergens = forms.MultipleChoiceField(
        label="Allergens",
        choices=ALLERGENS,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "check-grid"}),
        help_text="Tick every major allergen in this dish.",
    )
    dietary_tags = forms.MultipleChoiceField(
        label="Dietary tags (cook-declared, not verified)",
        choices=DIETARY_TAGS,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "check-grid"}),
    )
    allergens_complete = forms.BooleanField(
        label="This allergen list is complete",
        error_messages={"required": "Confirm that the allergen list is complete."},
    )

    class Meta:
        model = MenuItem
        fields = [
            "name",
            "meal_type",
            "course",
            "description",
            "ingredients",
            "allergens",
            "dietary_tags",
            "is_specialty",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "ingredients": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {"is_specialty": "This is my specialty for this meal"}
        help_texts = {
            "ingredients": "Separate them with commas. Diners can search for them.",
            "is_specialty": "One specialty per meal type.",
        }

    def __init__(self, cook: CookProfile, *args, **kwargs):
        self.cook = cook
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        meal, name = cleaned.get("meal_type"), cleaned.get("name")
        others = MenuItem.objects.filter(cook=self.cook, is_active=True).exclude(pk=self.instance.pk)
        if meal and name and others.filter(meal_type=meal, name__iexact=name).exists():
            self.add_error("name", "You already have a dish with this name for this meal.")
        if meal and cleaned.get("is_specialty") and others.filter(meal_type=meal, is_specialty=True).exists():
            label = MealType(meal).label.lower()
            self.add_error("is_specialty", f"You already have a {label} specialty. Untick it on that dish first.")
        if self.instance.pk and "allergens" in self.changed_data and self._has_active_bookings():
            self.add_error(
                "allergens",
                "Allergens are locked while this dish is on a meal with requested or confirmed bookings, "
                "because those diners agreed to the list they saw.",
            )
        return cleaned

    def _has_active_bookings(self) -> bool:
        return Booking.objects.filter(offering__items=self.instance, status__in=Booking.ACTIVE).exists()

    def save(self, commit: bool = True) -> MenuItem:
        self.instance.cook = self.cook
        self.instance.allergens_confirmed_at = timezone.now()
        return super().save(commit)


class OfferingForm(forms.ModelForm):
    """A dated meal. Money is entered in dollars and stored as integer cents (plan 3.5)."""

    items = forms.ModelMultipleChoiceField(
        label="Dishes",
        queryset=MenuItem.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "check-grid"}),
        help_text="Pick dishes from your menu for this meal type.",
    )
    capacity = forms.IntegerField(label="Seats", min_value=1, max_value=12, help_text="1 to 12 diners.")
    grocery_estimate = forms.DecimalField(
        label="Grocery estimate ($)",
        min_value=0,
        max_value=200,
        max_digits=5,
        decimal_places=2,
        help_text="What the groceries for this meal cost, up to $200.00.",
    )
    share_per_seat = forms.DecimalField(
        label="Grocery share per seat ($)",
        required=False,
        min_value=0,
        max_digits=5,
        decimal_places=2,
    )
    bring_list = forms.CharField(
        label="Bring list",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text=(
            "One item per line, for example “1 lb spaghetti”. A diner can bring one item instead of paying a share."
        ),
    )

    class Meta:
        model = Offering
        fields = ["title", "meal_type", "serve_at", "booking_cutoff_at", "capacity", "fulfillment", "pickup_note"]
        widgets = {
            "serve_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DATETIME_LOCAL),
            "booking_cutoff_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DATETIME_LOCAL),
            "fulfillment": forms.RadioSelect,
        }
        labels = {"serve_at": "Serve time", "booking_cutoff_at": "Booking cutoff", "pickup_note": "Pickup note"}
        help_texts = {
            "booking_cutoff_at": "Requests close at this time. It must be at or before the serve time.",
            "pickup_note": "Private: shown only to you and to confirmed diners.",
        }

    def __init__(self, cook: CookProfile, *args, **kwargs):
        self.cook = cook
        super().__init__(*args, **kwargs)
        offering = self.instance
        # Only this cook's dishes (AZ-07); an archived dish already on the meal stays selectable.
        on_this_meal = Q(offerings=offering) if offering.pk else Q(pk__in=[])
        self.fields["items"].queryset = MenuItem.objects.filter(Q(is_active=True) | on_this_meal, cook=cook).distinct()
        share_help = "Leave blank to use the suggestion: the grocery estimate ÷ (seats + 1), because you eat too."
        if offering.pk:
            self.initial.setdefault("items", list(offering.items.all()))
            self.initial.setdefault("grocery_estimate", _dollars(offering.grocery_estimate_cents))
            self.initial.setdefault("share_per_seat", _dollars(offering.share_per_seat_cents))
            self.initial.setdefault("bring_list", "\n".join(n.label for n in offering.open_needs))
            claimed = [n.label for n in offering.needs.all() if n.claimed_by_booking_id]
            if claimed:
                # Django's field template marks help text safe, so escape the cook's own labels.
                kept = escape("; ".join(claimed))
                self.fields["bring_list"].help_text += f" Already claimed by a diner, so kept: {kept}."
            suggested = suggested_share_cents(offering.grocery_estimate_cents, offering.capacity)
            share_help = f"Suggested share: {format_cents(suggested)} (the grocery estimate ÷ (seats + 1))."
        self.fields["share_per_seat"].help_text = share_help + " Enter 0 for no cash share."

    def clean_bring_list(self) -> list[str]:
        labels = [line.strip() for line in self.cleaned_data["bring_list"].splitlines() if line.strip()]
        if len(labels) > MAX_BRING_ITEMS:
            raise forms.ValidationError(f"Keep the bring list to {MAX_BRING_ITEMS} items.")
        if any(len(label) > 80 for label in labels):
            raise forms.ValidationError("Keep each bring-list item under 80 characters.")
        return labels

    def clean(self):
        cleaned = super().clean()
        serve_at, cutoff = cleaned.get("serve_at"), cleaned.get("booking_cutoff_at")
        if serve_at and not self.instance.pk and serve_at <= timezone.now():
            self.add_error("serve_at", "The serve time must be in the future.")
        elif serve_at and cutoff and cutoff > serve_at:
            self.add_error("booking_cutoff_at", "The booking cutoff must be at or before the serve time.")

        meal, items = cleaned.get("meal_type"), cleaned.get("items")
        if meal and items and any(item.meal_type != meal for item in items):
            self.add_error("items", f"Pick only {MealType(meal).label.lower()} dishes for a {meal} meal.")

        estimate, capacity, share = cleaned.get("grocery_estimate"), cleaned.get("capacity"), None
        if estimate is not None and capacity:
            estimate_cents = _cents(estimate)
            share = cleaned.get("share_per_seat")
            share_cents = suggested_share_cents(estimate_cents, capacity) if share is None else _cents(share)
            if share_cents * capacity > estimate_cents:
                most = format_cents(estimate_cents // capacity)
                self.add_error("share_per_seat", f"{NO_PROFIT} The most per seat is {most}.")
            self.instance.grocery_estimate_cents = estimate_cents
            self.instance.share_per_seat_cents = share_cents
        return cleaned

    @transaction.atomic
    def save(self, commit: bool = True) -> Offering:
        offering = super().save(commit=False)
        offering.cook = self.cook
        offering.save()
        offering.items.set(self.cleaned_data["items"])
        # Claimed bring-list items stay; the open ones are replaced by the edited list.
        offering.needs.filter(claimed_by_booking__isnull=True).delete()
        OfferingNeed.objects.bulk_create(
            OfferingNeed(offering=offering, label=label) for label in self.cleaned_data["bring_list"]
        )
        return offering
