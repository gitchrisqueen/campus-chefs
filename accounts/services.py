from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from meals.models import OfferingNeed

from .models import User


@transaction.atomic
def delete_account(user: User) -> None:
    """Anonymize an account (plan 5.4, the diner path; the cook path arrives with ACCT-03).

    Past bookings and reviews stay, because they belong to the other student too.
    """
    active = Booking.objects.filter(diner=user, status__in=Booking.ACTIVE)
    OfferingNeed.objects.filter(claimed_by_booking__in=active).update(claimed_by_booking=None)
    active.update(status=Booking.Status.CANCELLED, cancelled_by=Booking.Actor.DINER, closed_at=timezone.now())

    user.email = f"deleted-{user.pk}@invalid.example"
    user.first_name = "Former student"  # public_name shows first_name alone when last_name is empty
    user.last_name = ""
    user.set_unusable_password()  # also ends every other session (session auth hash)
    user.is_active = False
    user.save()
