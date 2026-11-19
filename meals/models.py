from django.apps import apps
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import F, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce, Lower

ALLERGENS = [
    ("milk", "Milk"),
    ("egg", "Egg"),
    ("fish", "Fish"),
    ("crustacean_shellfish", "Crustacean shellfish"),
    ("tree_nuts", "Tree nuts"),
    ("peanuts", "Peanuts"),
    ("wheat", "Wheat"),
    ("soy", "Soy"),
    ("sesame", "Sesame"),
]
DIETARY_TAGS = [
    ("vegetarian", "Vegetarian"),
    ("vegan", "Vegan"),
    ("dairy_free", "Dairy-free"),
    ("gluten_free", "Gluten-free"),
]


class MealType(models.TextChoices):
    BREAKFAST = "breakfast", "Breakfast"
    LUNCH = "lunch", "Lunch"
    DINNER = "dinner", "Dinner"


class Course(models.TextChoices):
    MAIN = "main", "Main"
    SIDE = "side", "Side"


def _in(field: str, choices) -> Q:
    return Q(**{f"{field}__in": [value for value, _ in choices]})


class Campus(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    timezone = models.CharField(max_length=64, default="America/New_York")

    class Meta:
        verbose_name_plural = "campuses"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class CookProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True, related_name="cook_profile"
    )
    bio = models.CharField(max_length=500, blank=True)
    food_safety_ack_at = models.DateTimeField()

    def __str__(self) -> str:
        return f"Cook {self.user.public_name}"


class MenuItem(models.Model):
    cook = models.ForeignKey(CookProfile, on_delete=models.CASCADE, related_name="menu_items")
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=500, blank=True)
    ingredients = models.CharField(max_length=500, blank=True)
    meal_type = models.CharField(max_length=10, choices=MealType.choices)
    course = models.CharField(max_length=4, choices=Course.choices)
    allergens = ArrayField(models.CharField(max_length=24, choices=ALLERGENS), default=list, blank=True)
    allergens_confirmed_at = models.DateTimeField()
    dietary_tags = ArrayField(models.CharField(max_length=16, choices=DIETARY_TAGS), default=list, blank=True)
    is_specialty = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["meal_type", "course", "name"]
        constraints = [
            models.UniqueConstraint(
                F("cook"),
                Lower("name"),
                F("meal_type"),
                condition=Q(is_active=True),
                name="menuitem_unique_active_name_per_meal",
            ),
            models.UniqueConstraint(
                fields=["cook", "meal_type"],
                condition=Q(is_specialty=True, is_active=True),
                name="menuitem_one_specialty_per_meal",
            ),
            models.CheckConstraint(condition=_in("meal_type", MealType.choices), name="menuitem_meal_type_valid"),
            models.CheckConstraint(condition=_in("course", Course.choices), name="menuitem_course_valid"),
            models.CheckConstraint(
                condition=Q(allergens__contained_by=[v for v, _ in ALLERGENS]), name="menuitem_allergens_valid"
            ),
            models.CheckConstraint(
                condition=Q(dietary_tags__contained_by=[v for v, _ in DIETARY_TAGS]),
                name="menuitem_dietary_tags_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        parts = [p.strip().lower() for p in self.ingredients.split(",")]
        self.ingredients = ", ".join(dict.fromkeys(p for p in parts if p))

    @property
    def allergen_labels(self) -> list[str]:
        names = dict(ALLERGENS)
        return [names[a].lower() for a in self.allergens]

    @property
    def dietary_labels(self) -> list[str]:
        names = dict(DIETARY_TAGS)
        return [names[t] for t in self.dietary_tags]


class Fulfillment(models.TextChoices):
    PICKUP = "pickup", "Pickup"
    DINE_IN = "dine_in", "Dine-in"


class OfferingStatus(models.TextChoices):
    OPEN = "open", "Open"
    CANCELLED = "cancelled", "Cancelled"


class OfferingQuerySet(models.QuerySet):
    def with_seats_taken(self):
        """Annotate `seats_taken`: seats held by requested and confirmed bookings (plan 2.3)."""
        taken = (
            apps.get_model("bookings", "Booking")
            .objects.filter(offering=OuterRef("pk"), status__in=["requested", "confirmed"])
            .values("offering")
            .annotate(total=Sum("seats"))
            .values("total")
        )
        return self.annotate(seats_taken=Coalesce(Subquery(taken), 0))

    def for_listing(self):
        """What an offering card needs: cook, campus, dishes, bring list and seats taken."""
        return self.select_related("cook__user__campus").prefetch_related("items", "needs").with_seats_taken()


class Offering(models.Model):
    Fulfillment = Fulfillment
    Status = OfferingStatus

    cook = models.ForeignKey(CookProfile, on_delete=models.CASCADE, related_name="offerings")
    title = models.CharField(max_length=80)
    meal_type = models.CharField(max_length=10, choices=MealType.choices)
    items = models.ManyToManyField(MenuItem, through="OfferingItem", related_name="offerings")
    serve_at = models.DateTimeField()
    booking_cutoff_at = models.DateTimeField()
    capacity = models.PositiveSmallIntegerField()
    fulfillment = models.CharField(max_length=8, choices=Fulfillment.choices, default=Fulfillment.PICKUP)
    pickup_note = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    # Grocery cost-sharing (plan 3.5): integer cents, never money movement.
    grocery_estimate_cents = models.PositiveIntegerField(default=0)
    share_per_seat_cents = models.PositiveIntegerField(default=0)

    objects = OfferingQuerySet.as_manager()

    class Meta:
        ordering = ["serve_at"]
        indexes = [models.Index(fields=["status", "serve_at"], name="offering_status_serve_idx")]
        constraints = [
            models.CheckConstraint(
                condition=Q(booking_cutoff_at__lte=F("serve_at")), name="offering_cutoff_before_serve"
            ),
            models.CheckConstraint(condition=Q(capacity__gte=1, capacity__lte=12), name="offering_capacity_1_12"),
            models.CheckConstraint(condition=_in("meal_type", MealType.choices), name="offering_meal_type_valid"),
            models.CheckConstraint(
                condition=_in("fulfillment", Fulfillment.choices), name="offering_fulfillment_valid"
            ),
            models.CheckConstraint(condition=_in("status", OfferingStatus.choices), name="offering_status_valid"),
            models.CheckConstraint(
                condition=Q(grocery_estimate_cents__gte=0, grocery_estimate_cents__lte=20_000),
                name="offering_grocery_estimate_0_200_dollars",
            ),
            models.CheckConstraint(
                condition=Q(grocery_estimate_cents__gte=F("share_per_seat_cents") * F("capacity")),
                name="offering_no_profit",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.serve_at:%Y-%m-%d %H:%M})"

    @property
    def is_free(self) -> bool:
        """No cash share and no bring list (plan 3.5)."""
        return self.share_per_seat_cents == 0 and not self.needs.all()

    @property
    def open_needs(self) -> list[OfferingNeed]:
        return [need for need in self.needs.all() if need.claimed_by_booking_id is None]

    @property
    def allergen_labels(self) -> list[str]:
        """Every allergen declared on any dish of this meal, in first-seen order."""
        return list(dict.fromkeys(label for item in self.items.all() for label in item.allergen_labels))

    @property
    def seats_left(self) -> int:
        """Needs the `with_seats_taken()` annotation."""
        return max(self.capacity - self.seats_taken, 0)


class OfferingItem(models.Model):
    offering = models.ForeignKey(Offering, on_delete=models.CASCADE)
    item = models.ForeignKey(MenuItem, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["offering", "item"], name="offeringitem_unique")]

    def __str__(self) -> str:
        return f"{self.offering_id}:{self.item_id}"


class OfferingNeed(models.Model):
    """One line of the cook's bring list (plan 3.5)."""

    offering = models.ForeignKey(Offering, on_delete=models.CASCADE, related_name="needs")
    label = models.CharField(max_length=80)
    claimed_by_booking = models.OneToOneField(
        "bookings.Booking", null=True, blank=True, on_delete=models.SET_NULL, related_name="claimed_need"
    )

    def __str__(self) -> str:
        return self.label
