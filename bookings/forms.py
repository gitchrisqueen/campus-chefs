from decimal import Decimal

from django import forms

from meals.models import Offering
from meals.money import format_cents

from .models import Booking, Review

C = Booking.Contribution


class BookingRequestForm(forms.Form):
    """A seat request (plan 2.3, 3.5). Not a ModelForm: status, diner and offering never come from the POST (AZ-08)."""

    seats = forms.TypedChoiceField(label="Seats", choices=[(n, str(n)) for n in range(1, 5)], coerce=int, initial=1)
    contribution = forms.ChoiceField(label="How you'll chip in", widget=forms.RadioSelect)
    need = forms.ModelChoiceField(
        label="Item you'll bring", required=False, queryset=None, empty_label="Pick an item from the bring list"
    )
    terms = forms.CharField(
        label="Your terms",
        required=False,
        max_length=280,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="For example “a salad and $2”. Only the cook sees them.",
    )
    amount = forms.DecimalField(
        label="Amount you offer ($)",
        required=False,
        min_value=0,
        max_digits=5,
        decimal_places=2,
        help_text="You pay the cook in person; nothing is paid on this site.",
    )
    allergen_ack = forms.BooleanField(
        error_messages={"required": "Confirm that you have read the allergens for this meal."},
    )

    def __init__(self, offering: Offering, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.offering = offering
        allergens = ", ".join(offering.allergen_labels) or "none declared"
        label = f"I have read the allergens (contains: {allergens}). They are cook-declared, not a safety guarantee."
        self.fields["allergen_ack"].label = label
        if offering.is_free:
            for name in ("contribution", "need", "terms", "amount"):
                del self.fields[name]
            return
        choices = []
        if offering.share_per_seat_cents:
            share = format_cents(offering.share_per_seat_cents)
            choices.append((C.SHARE, f"Grocery share: {share} per seat, paid to the cook at pickup"))
        open_needs = offering.needs.filter(claimed_by_booking__isnull=True)
        if open_needs.exists():
            choices.append((C.INGREDIENTS, "Bring an item from the bring list instead"))
            self.fields["need"].queryset = open_needs
        else:
            del self.fields["need"]
        choices.append((C.CUSTOM, "Propose your own terms"))
        self.fields["contribution"].choices = choices
        self.fields["contribution"].initial = choices[0][0]

    def clean(self):
        cleaned = super().clean()
        contribution = cleaned.get("contribution")
        if contribution == C.INGREDIENTS and not cleaned.get("need"):
            self.add_error("need", "Pick the item you'll bring.")
        if contribution == C.CUSTOM and not cleaned.get("terms", "").strip():
            self.add_error("terms", "Describe the terms you propose.")
        return cleaned

    def service_kwargs(self) -> dict:
        """Keyword arguments for `services.request_booking`."""
        data = self.cleaned_data
        contribution = data.get("contribution", C.NONE)
        amount = data.get("amount") or Decimal(0)
        custom = contribution == C.CUSTOM
        return {
            "seats": data["seats"],
            "contribution": contribution,
            "need": data.get("need") if contribution == C.INGREDIENTS else None,
            "terms": data.get("terms", "") if custom else "",
            "amount_cents": int(amount * 100) if custom else 0,
        }


class ReviewForm(forms.ModelForm):
    """A diner's review. The booking, `hidden_at` and the dates never come from the POST (AZ-08)."""

    rating = forms.TypedChoiceField(
        label="Rating",
        choices=[(n, f"{n} star{'s' if n > 1 else ''}") for n in range(1, 6)],
        coerce=int,
        widget=forms.RadioSelect,
        help_text="1 star is poor, 5 stars is great.",
    )

    class Meta:
        model = Review
        fields = ["rating", "the_good", "the_bad"]
        labels = {"the_good": "The good", "the_bad": "The bad"}
        widgets = {"the_good": forms.Textarea(attrs={"rows": 3}), "the_bad": forms.Textarea(attrs={"rows": 3})}
