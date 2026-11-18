"""Small explicit builders for tests. No Faker: every value is visible here."""

from datetime import timedelta
from itertools import count

from django.utils import timezone

from accounts.models import User
from bookings.models import Booking
from meals.models import Campus, CookProfile, MenuItem, Offering

_seq = count(1)


def campus(slug: str = "larkspur", name: str = "Larkspur State University (Demo)") -> Campus:
    return Campus.objects.get_or_create(slug=slug, defaults={"name": name})[0]


def user(
    first: str = "Ava", last: str = "Reyes", email: str | None = None, password: str | None = None, **extra
) -> User:
    n = next(_seq)
    return User.objects.create_user(
        email or f"user{n}@larkspur.example",
        password,
        first_name=first,
        last_name=last,
        campus=extra.pop("campus", None) or campus(),
        adult_attested_at=timezone.now(),
        **extra,
    )


def cook(**kwargs) -> CookProfile:
    return CookProfile.objects.create(user=user(**kwargs), food_safety_ack_at=timezone.now())


def menu_item(cook_profile: CookProfile, name: str = "Buttermilk Pancakes", **extra) -> MenuItem:
    defaults = {"meal_type": "breakfast", "course": "main", "allergens_confirmed_at": timezone.now()}
    return MenuItem.objects.create(cook=cook_profile, name=name, **{**defaults, **extra})


def offering(cook_profile: CookProfile, *, days_ahead: int = 2, **extra) -> Offering:
    serve_at = timezone.now() + timedelta(days=days_ahead)
    defaults = {
        "title": "Pancake Breakfast",
        "meal_type": "breakfast",
        "serve_at": serve_at,
        "booking_cutoff_at": serve_at - timedelta(hours=2),
        "capacity": 4,
        "grocery_estimate_cents": 2000,
        "share_per_seat_cents": 400,
    }
    return Offering.objects.create(cook=cook_profile, **{**defaults, **extra})


def booking(offering_obj: Offering, diner: User, **extra) -> Booking:
    defaults = {"seats": 1, "allergen_ack_at": timezone.now()}
    return Booking.objects.create(offering=offering_obj, diner=diner, **{**defaults, **extra})
