"""The booking state machine (plan 3.3). Every write runs in one transaction under a lock on the offering."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from meals.models import Offering

from . import contributions
from .errors import BookingError, BookingRejected, Forbidden, NotParticipant
from .models import Booking, Review

S = Booking.Status
A = Booking.Actor

# Exactly the 5 edges of plan 3.3, and who may take each one.
ALLOWED: dict[tuple[str, str], frozenset[str]] = {
    (S.REQUESTED, S.CONFIRMED): frozenset({A.COOK}),
    (S.REQUESTED, S.DECLINED): frozenset({A.COOK}),
    (S.REQUESTED, S.CANCELLED): frozenset({A.DINER, A.COOK, A.SYSTEM}),
    (S.CONFIRMED, S.CANCELLED): frozenset({A.DINER, A.COOK, A.SYSTEM}),
    (S.CONFIRMED, S.COMPLETED): frozenset({A.COOK}),
}


def role_of(booking: Booking, actor) -> str | None:
    """`actor` is a user, or `Booking.Actor.SYSTEM`. None means not a participant."""
    if isinstance(actor, str):
        return A.SYSTEM if actor == A.SYSTEM else None
    if actor.pk == booking.diner_id:
        return A.DINER
    if actor.pk == booking.offering.cook_id:
        return A.COOK
    return None


def _seats(bookings) -> int:
    return bookings.aggregate(total=Sum("seats"))["total"] or 0


def request_booking(
    offering: Offering,
    diner,
    seats: int,
    contribution: str = Booking.Contribution.NONE,
    *,
    need=None,
    terms: str = "",
    amount_cents: int = 0,
    now=None,
) -> Booking:
    """A diner asks for seats (plan 2.3). Raises BookingRejected with a message for the form."""
    now = now or timezone.now()
    with transaction.atomic():
        offering = Offering.objects.select_for_update().get(pk=offering.pk)
        if offering.status != Offering.Status.OPEN or now >= offering.booking_cutoff_at:
            raise BookingRejected("Requests for this meal are closed.")
        if offering.cook_id == diner.pk:
            raise BookingRejected("You can't book your own meal.")
        if not 1 <= seats <= 4:
            raise BookingRejected("Book 1 to 4 seats.", "seats")
        active = offering.bookings.filter(status__in=Booking.ACTIVE)
        if active.filter(diner=diner).exists():
            raise BookingRejected("You already have a request for this meal.")
        left = offering.capacity - _seats(active)  # re-checked under the lock (BOOK-06)
        if seats > left:
            message = f"Only {left} seat{'' if left == 1 else 's'} left." if left > 0 else "This meal is full."
            raise BookingRejected(message, "seats")
        share_cents = contributions.contribution_cents(
            offering, seats, contribution, need=need, terms=terms, amount_cents=amount_cents
        )
        booking = Booking.objects.create(
            offering=offering,
            diner=diner,
            seats=seats,
            status=S.REQUESTED,
            allergen_ack_at=now,
            contribution=contribution,
            share_cents=share_cents,
            terms=terms.strip() if contribution == Booking.Contribution.CUSTOM else "",
        )
        if booking.contribution == Booking.Contribution.INGREDIENTS:
            contributions.claim_need(offering, need, booking)
    return booking


def check(booking: Booking, offering: Offering, to: str, role: str, now) -> None:
    """Raise unless `role` may move `booking` to `to` at `now`. Edge first (409), then role (403), then time (409)."""
    allowed = ALLOWED.get((booking.status, to))
    if allowed is None:
        raise BookingError(f"A {booking.get_status_display().lower()} booking can't be changed that way.")
    if role not in allowed:
        raise Forbidden("Only the cook can do that." if role == A.DINER else "You can't make that change.")
    if to == S.CONFIRMED:
        if now >= offering.serve_at:
            raise BookingError("This meal has already been served.")
        confirmed = _seats(offering.bookings.filter(status=S.CONFIRMED).exclude(pk=booking.pk))
        if confirmed + booking.seats > offering.capacity:
            raise BookingError("There are not enough seats left to confirm this request.")
    elif to == S.CANCELLED:
        diner_late = booking.status == S.CONFIRMED and role == A.DINER
        deadline = offering.booking_cutoff_at if diner_late else offering.serve_at
        if now >= deadline:
            raise BookingError("It is too late to cancel this booking.")
    elif to == S.COMPLETED and now < offering.serve_at:
        raise BookingError("You can mark it completed after the meal is served.")


def available(booking: Booking, role: str | None, now=None) -> list[str]:
    """The statuses this role can move the booking to right now, for the action buttons."""
    now = now or timezone.now()
    targets = []
    for (source, to), roles in ALLOWED.items():
        if source != booking.status or role not in roles:
            continue
        try:
            check(booking, booking.offering, to, role, now)
        except BookingError:
            continue
        targets.append(to)
    return targets


def transition(booking: Booking, to: str, actor, now=None) -> Booking:
    """Move a booking along one edge of the state machine, writing the status and its timestamp together."""
    now = now or timezone.now()
    role = role_of(booking, actor)
    if role is None:
        raise NotParticipant("Not found.")
    with transaction.atomic():
        offering = Offering.objects.select_for_update().get(pk=booking.offering_id)
        booking.refresh_from_db()
        check(booking, offering, to, role, now)
        booking.status = to
        if to in (S.CONFIRMED, S.DECLINED):
            booking.decided_at = now
        else:
            booking.closed_at = now
        if to == S.CANCELLED:
            booking.cancelled_by = role
        booking.save(update_fields=["status", "decided_at", "closed_at", "cancelled_by"])
        if to in (S.DECLINED, S.CANCELLED):
            contributions.release_claim(booking)
    return booking


def cancel_offering(offering: Offering, now=None) -> Offering:
    """The cook calls off a meal: every active booking is system-cancelled and its claim released (BOOK-12)."""
    now = now or timezone.now()
    with transaction.atomic():
        offering = Offering.objects.select_for_update().get(pk=offering.pk)
        if offering.status == Offering.Status.CANCELLED:
            return offering
        if now >= offering.serve_at:
            raise BookingError("This meal has already been served, so it can't be cancelled.")
        for booking in offering.bookings.filter(status__in=Booking.ACTIVE):
            transition(booking, S.CANCELLED, A.SYSTEM, now)
        offering.status = Offering.Status.CANCELLED
        offering.save(update_fields=["status"])
    return offering


REVIEW_WINDOW = timedelta(days=14)


def review_block(booking: Booking, user, now=None) -> BookingError | None:
    """Why `user` can't review `booking` now, or None when they can (REV-02, REV-03, REV-05, REV-07)."""
    now = now or timezone.now()
    role = role_of(booking, user)
    if role is None:
        return NotParticipant("Not found.")
    if role != A.DINER:
        return Forbidden("Only the diner can review a meal.")
    if booking.status != S.COMPLETED:
        return Forbidden("You can review a meal once it is completed.")
    if Review.objects.filter(booking=booking).exists():
        return BookingError("You already reviewed this meal.")
    if booking.closed_at is None or now > booking.closed_at + REVIEW_WINDOW:
        return BookingError("The 14 days to review this meal have passed.")
    return None


def submit_review(booking: Booking, user, rating: int, the_good: str = "", the_bad: str = "", now=None) -> Review:
    """The diner reviews a completed booking, once, within 14 days of closing (plan 1.2)."""
    with transaction.atomic():
        booking = Booking.objects.select_for_update().select_related("offering").get(pk=booking.pk)
        error = review_block(booking, user, now)
        if error:
            raise error
        return Review.objects.create(booking=booking, rating=rating, the_good=the_good, the_bad=the_bad)
