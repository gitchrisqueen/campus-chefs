from django.db import transaction
from django.utils import timezone

from bookings import services as booking_services
from bookings.models import Booking
from meals.models import CookProfile, Offering, OfferingNeed

from .models import User


@transaction.atomic
def delete_account(user: User) -> None:
    """Anonymize an account (plan 5.4).

    Diner path: the user's active bookings are cancelled. Cook path (ACCT-03): every upcoming meal is
    cancelled, which system-cancels its bookings, and the menu is archived. Past bookings and reviews
    stay, because they belong to the other student too.
    """
    now = timezone.now()
    active = Booking.objects.filter(diner=user, status__in=Booking.ACTIVE)
    OfferingNeed.objects.filter(claimed_by_booking__in=active).update(claimed_by_booking=None)
    active.update(status=Booking.Status.CANCELLED, cancelled_by=Booking.Actor.DINER, closed_at=now)

    cook = CookProfile.objects.filter(user=user).first()
    if cook is not None:
        for offering in cook.offerings.filter(status=Offering.Status.OPEN, serve_at__gt=now):
            booking_services.cancel_offering(offering, now=now)
        cook.menu_items.filter(is_active=True).update(is_active=False, is_specialty=False)

    user.email = f"deleted-{user.pk}@invalid.example"
    user.first_name = "Former student"  # public_name shows first_name alone when last_name is empty
    user.last_name = ""
    user.set_unusable_password()  # also ends every other session (session auth hash)
    user.is_active = False
    user.save()
