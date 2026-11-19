from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from meals.money import format_cents


def _in(field: str, choices) -> Q:
    return Q(**{f"{field}__in": [value for value, _ in choices]})


class BookingStatus(models.TextChoices):
    REQUESTED = "requested", "Requested"
    CONFIRMED = "confirmed", "Confirmed"
    DECLINED = "declined", "Declined"
    CANCELLED = "cancelled", "Cancelled"
    COMPLETED = "completed", "Completed"


class BookingActor(models.TextChoices):
    DINER = "diner", "Diner"
    COOK = "cook", "Cook"
    SYSTEM = "system", "System"


class BookingContribution(models.TextChoices):
    NONE = "none", "None (free meal)"
    SHARE = "share", "Grocery share"
    INGREDIENTS = "ingredients", "Bring an item"
    CUSTOM = "custom", "Custom terms"


class Booking(models.Model):
    Status = BookingStatus
    Actor = BookingActor
    Contribution = BookingContribution

    ACTIVE = (Status.REQUESTED, Status.CONFIRMED)

    offering = models.ForeignKey("meals.Offering", on_delete=models.PROTECT, related_name="bookings")
    diner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings")
    seats = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REQUESTED)
    allergen_ack_at = models.DateTimeField()
    note = models.CharField(max_length=280, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    # NULL means "not cancelled"; the cancelled_by CHECK relies on it.
    cancelled_by = models.CharField(max_length=6, choices=Actor.choices, null=True, blank=True)  # noqa: DJ001
    # Grocery contribution (plan 3.5): recorded, never charged.
    contribution = models.CharField(max_length=12, choices=Contribution.choices, default=Contribution.NONE)
    share_cents = models.PositiveIntegerField(default=0)
    terms = models.CharField(max_length=280, blank=True)
    contribution_received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["diner"], name="booking_diner_idx"),
            models.Index(fields=["offering", "status"], name="booking_offering_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["offering", "diner"],
                condition=Q(status__in=["requested", "confirmed"]),
                name="booking_one_active_per_diner",
            ),
            models.CheckConstraint(condition=Q(seats__gte=1, seats__lte=4), name="booking_seats_1_4"),
            models.CheckConstraint(condition=_in("status", BookingStatus.choices), name="booking_status_valid"),
            models.CheckConstraint(
                condition=_in("contribution", BookingContribution.choices), name="booking_contribution_valid"
            ),
            models.CheckConstraint(
                condition=(Q(status="cancelled") & Q(cancelled_by__in=[v for v, _ in BookingActor.choices]))
                | (~Q(status="cancelled") & Q(cancelled_by__isnull=True)),
                name="booking_cancelled_by_iff_cancelled",
            ),
            models.CheckConstraint(
                condition=Q(share_cents=0) | Q(contribution__in=["share", "custom"]),
                name="booking_share_only_for_share_or_custom",
            ),
            models.CheckConstraint(
                condition=~Q(contribution="custom") | ~Q(terms="") | ~Q(status__in=["requested", "confirmed"]),
                name="booking_custom_needs_terms",
            ),
        ]

    def __str__(self) -> str:
        return f"Booking {self.pk} ({self.status})"

    def get_absolute_url(self) -> str:
        return reverse("booking_detail", args=[self.pk])

    @property
    def status_label(self) -> str:
        """A request whose serve time has passed reads "Expired"; it is not a stored status (plan 3.3)."""
        if self.status == self.Status.REQUESTED and self.offering.serve_at <= timezone.now():
            return "Expired"
        return self.get_status_display()

    @property
    def contribution_text(self) -> str:
        """How the diner chips in, in the words the booking page uses (plan 3.5)."""
        C = self.Contribution
        if self.contribution == C.SHARE:
            due = ", pay the cook in person" if self.status in self.ACTIVE else ""
            return f"Grocery share: {format_cents(self.share_cents)}{due}"
        if self.contribution == C.INGREDIENTS:
            need = getattr(self, "claimed_need", None)  # released when declined or cancelled
            return f"Bring: {need.label}" if need else "Bring: an item from the bring list (released)"
        if self.contribution == C.CUSTOM:
            agreed = "Agreed" if self.status in (self.Status.CONFIRMED, self.Status.COMPLETED) else "Offered"
            amount = f"{format_cents(self.share_cents)} + " if self.share_cents else ""
            return f"{agreed}: {amount}{self.terms or 'Custom terms (removed)'}"
        return "Free meal: nothing to chip in"


class Review(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.PROTECT, related_name="review")
    rating = models.PositiveSmallIntegerField()
    the_good = models.CharField(max_length=500, blank=True)
    the_bad = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    hidden_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_5")]

    def __str__(self) -> str:
        return f"Review {self.pk} ({self.rating}/5)"
