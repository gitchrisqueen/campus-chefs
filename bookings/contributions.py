"""Grocery contributions (plan 3.5). The app records who chips in what; it never moves money (D10)."""

from django.db import transaction
from django.db.models import OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from meals.models import Offering, OfferingNeed
from meals.money import format_cents

from .errors import BookingError, BookingRejected, Forbidden, NotParticipant
from .models import Booking

NO_PROFIT = "Diners together can't pay more than the groceries cost."
COUNTED = (Booking.Status.CONFIRMED, Booking.Status.COMPLETED)


def share_snapshot(offering: Offering, seats: int) -> int:
    """The share frozen on the booking. Later edits to the offering never change it (CONTRIB-03)."""
    return seats * offering.share_per_seat_cents


def custom_cap_cents(offering: Offering, seats: int) -> int:
    """The most a custom offer may name: the no-profit cap per seat, times the seats (CONTRIB-12)."""
    return seats * (offering.grocery_estimate_cents // offering.capacity)


def contribution_cents(
    offering: Offering, seats: int, contribution: str, *, need, terms: str, amount_cents: int
) -> int:
    """Check the diner's choice against the offering and return the `share_cents` to store."""
    C = Booking.Contribution
    if offering.is_free:
        if contribution != C.NONE:
            raise BookingRejected("This meal is free, so there is nothing to chip in.", "contribution")
        return 0
    if contribution == C.SHARE and offering.share_per_seat_cents:
        return share_snapshot(offering, seats)
    if contribution == C.INGREDIENTS:
        if need is None:
            raise BookingRejected("Pick the item you'll bring.", "need")
        return 0
    if contribution == C.CUSTOM:
        if not terms.strip():
            raise BookingRejected("Describe the terms you propose.", "terms")
        cap = custom_cap_cents(offering, seats)
        if amount_cents > cap:
            seat_word = "seat" if seats == 1 else "seats"
            raise BookingRejected(f"{NO_PROFIT} The most for {seats} {seat_word} is {format_cents(cap)}.", "amount")
        return amount_cents
    raise BookingRejected("Pick how you'll chip in for the groceries.", "contribution")


def claim_need(offering: Offering, need: OfferingNeed, booking: Booking) -> None:
    """Claim one open bring-list item. The conditional UPDATE means two claims can never both win (CONTRIB-04)."""
    claimed = OfferingNeed.objects.filter(pk=need.pk, offering=offering, claimed_by_booking__isnull=True).update(
        claimed_by_booking=booking
    )
    if not claimed:
        raise BookingRejected("Someone already claimed that item. Pick another.", "need")


def release_claim(booking: Booking) -> None:
    """Free the item a declined or cancelled booking had claimed (CONTRIB-05)."""
    OfferingNeed.objects.filter(claimed_by_booking=booking).update(claimed_by_booking=None)


def can_mark_received(booking: Booking) -> bool:
    return (
        booking.status in COUNTED
        and booking.contribution != Booking.Contribution.NONE
        and booking.contribution_received_at is None
    )


def mark_received(booking: Booking, actor, now=None) -> Booking:
    """The cook records that the diner's share or item arrived (CONTRIB-07). Not a status, so 3.3 is unchanged."""
    if actor.pk == booking.diner_id:
        raise Forbidden("Only the cook marks a contribution received.")
    if actor.pk != booking.offering.cook_id:
        raise NotParticipant("Not found.")
    with transaction.atomic():
        Offering.objects.select_for_update().get(pk=booking.offering_id)
        booking.refresh_from_db()
        if not can_mark_received(booking):
            raise BookingError("Only a confirmed or completed booking with something to receive can be marked.")
        booking.contribution_received_at = now or timezone.now()
        booking.save(update_fields=["contribution_received_at"])
    return booking


def _sum_shares(condition: Q) -> Coalesce:
    total = (
        Booking.objects.filter(condition, offering=OuterRef("pk"), status__in=COUNTED)
        .values("offering")
        .annotate(total=Sum("share_cents"))
        .values("total")
    )
    return Coalesce(Subquery(total), 0)


def with_totals(offerings):
    """Annotate `expected_cents` (confirmed shares) and `received_cents` for the kitchen line
    "Groceries $Z. Chip-ins received $Y of $X from confirmed diners." (CONTRIB-09)."""
    return offerings.annotate(
        expected_cents=_sum_shares(Q()),
        received_cents=_sum_shares(Q(contribution_received_at__isnull=False)),
    )
