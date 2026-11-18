"""Deterministic synthetic demo data (plan 3.4).

  seed_demo             seed an empty database (fails if data exists)
  seed_demo --if-empty  seed only when no campus exists (bootstrap_demo uses this)
  seed_demo --reset     wipe demo data and reseed; only with CC_DEMO_MODE=true

Times are relative to "now", so a fresh seed always has past, today and future offerings.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from bookings.models import Booking, Review
from core import seed_data as data
from meals.models import Campus, CookProfile, MenuItem, Offering, OfferingItem, OfferingNeed

TZ = ZoneInfo("America/New_York")


@dataclass
class OfferingSpec:
    cook: int
    meal: str
    title: str
    when: tuple[str, int, int]  # ("day", offset, hour) or ("hours", hours_from_now, 0)
    capacity: int
    estimate: int  # cents
    share: int  # cents per seat
    needs: int = 0
    fulfillment: str = "pickup"
    status: str = "open"
    # (diner index, seats, status, contribution, cancelled_by)
    bookings: list[tuple] = field(default_factory=list)


C, R, D, X, K = "completed", "requested", "declined", "cancelled", "confirmed"

# Diner 0 is the demo diner. Offering 0 is the demo cook's "yesterday" meal used by E2E-02,
# and offering 9 is the demo cook's future pancake breakfast used by E2E-01.
OFFERINGS = [
    OfferingSpec(0, "dinner", "Steak Night", ("day", -1, 18), 4, 2000, 400, bookings=[(0, 1, K, "share", None)]),
    OfferingSpec(
        1,
        "dinner",
        "Shrimp Stir-Fry Supper",
        ("day", -2, 19),
        6,
        3000,
        400,
        needs=1,
        bookings=[(1, 2, C, "share", None), (2, 1, C, "ingredients", None)],
    ),
    OfferingSpec(
        2,
        "lunch",
        "Grilled Cheese Lunch",
        ("day", -3, 12),
        4,
        0,
        0,
        bookings=[(3, 1, C, "none", None), (4, 2, C, "none", None)],
    ),
    OfferingSpec(
        3,
        "dinner",
        "Curry Night",
        ("day", -4, 18),
        5,
        2500,
        500,
        bookings=[(5, 2, C, "share", None), (6, 1, C, "custom", None)],
    ),
    OfferingSpec(
        4,
        "breakfast",
        "Weekend Waffles",
        ("day", -5, 10),
        4,
        1200,
        0,
        needs=2,
        bookings=[(7, 1, C, "ingredients", None), (8, 1, C, "ingredients", None)],
    ),
    OfferingSpec(
        5,
        "lunch",
        "Falafel Friday",
        ("day", -6, 13),
        6,
        1800,
        300,
        fulfillment="dine_in",
        bookings=[(9, 2, C, "share", None), (10, 2, C, "share", None)],
    ),
    OfferingSpec(
        6,
        "dinner",
        "Lasagna Night",
        ("day", -7, 18),
        4,
        2400,
        500,
        needs=1,
        bookings=[(11, 1, C, "share", None), (12, 2, C, "share", None)],
    ),
    OfferingSpec(
        7,
        "dinner",
        "Salmon Bowls",
        ("hours", 5, 0),
        6,
        3000,
        400,
        needs=2,
        bookings=[(1, 1, R, "share", None), (13, 1, K, "ingredients", None)],
    ),
    OfferingSpec(1, "lunch", "Soup and Sandwich", ("hours", 3, 0), 4, 0, 0, bookings=[(2, 1, R, "none", None)]),
    OfferingSpec(
        0, "breakfast", "Pancake Breakfast", ("day", 1, 9), 6, 2400, 400, needs=2, bookings=[(3, 2, R, "share", None)]
    ),
    OfferingSpec(
        1,
        "dinner",
        "Stir-Fry Night",
        ("day", 2, 19),
        5,
        2500,
        500,
        bookings=[(4, 2, K, "share", None), (5, 1, D, "share", None)],
    ),
    OfferingSpec(
        2,
        "lunch",
        "Panini Lunch",
        ("day", 3, 12),
        4,
        0,
        0,
        bookings=[(6, 1, R, "none", None), (7, 1, X, "none", "diner")],
    ),
    OfferingSpec(
        3,
        "dinner",
        "Bring-a-Thing Pasta Night",
        ("day", 4, 18),
        4,
        1500,
        0,
        needs=3,
        bookings=[(8, 1, R, "ingredients", None), (9, 1, R, "custom", None)],
    ),
    OfferingSpec(
        4, "breakfast", "Shakshuka Brunch", ("day", 5, 10), 4, 1200, 300, bookings=[(10, 1, X, "share", "cook")]
    ),
    OfferingSpec(5, "dinner", "Taco Tuesday", ("day", 6, 18), 6, 3600, 600, bookings=[(11, 2, R, "share", None)]),
    OfferingSpec(
        6, "lunch", "Wrap Lunch", ("day", 7, 12), 4, 1600, 400, needs=1, bookings=[(12, 1, K, "custom", None)]
    ),
]

CUSTOM_TERMS = [
    "I'll bring drinks and $2",
    "I'll do the dishes and bring dessert",
    "$3 plus a bag of ice",
]


class Command(BaseCommand):
    help = "Seed deterministic synthetic demo data."

    def add_arguments(self, parser):
        parser.add_argument("--if-empty", action="store_true", help="Seed only if no campus exists.")
        parser.add_argument("--reset", action="store_true", help="Delete demo data first (CC_DEMO_MODE only).")

    def handle(self, *args, if_empty=False, reset=False, **options):
        if reset and not settings.CC_DEMO_MODE:
            raise CommandError("--reset is only allowed with CC_DEMO_MODE=true")
        has_data = Campus.objects.exists()
        if has_data and if_empty:
            self.stdout.write("seed_demo: data present, skipping (--if-empty)")
            return
        if has_data and not reset:
            raise CommandError("data already present; use --reset (demo mode) to reseed")
        with transaction.atomic():
            if reset:
                self._wipe()
            counts = self._seed(timezone.now())
        self.stdout.write(self.style.SUCCESS("seed_demo: " + ", ".join(f"{k}={v}" for k, v in counts.items())))

    def _wipe(self) -> None:
        Review.objects.all().delete()
        OfferingNeed.objects.update(claimed_by_booking=None)
        Booking.objects.all().delete()
        Offering.objects.all().delete()
        MenuItem.objects.all().delete()
        User.objects.filter(is_staff=False).delete()
        Campus.objects.filter(users__isnull=True).delete()

    def _seed(self, now: datetime) -> dict[str, int]:
        rng = random.Random(2008)  # noqa: S311 - deterministic demo data, not security  # nosec B311
        campuses = {slug: Campus.objects.create(name=name, slug=slug) for name, slug in data.CAMPUSES}

        def make_user(row, joined_days_ago: int) -> User:
            email, first, last, campus_slug, classification = row
            user = User(
                email=email,
                first_name=first,
                last_name=last,
                campus=campuses[campus_slug],
                classification=classification,
                adult_attested_at=now - timedelta(days=joined_days_ago),
                date_joined=now - timedelta(days=joined_days_ago),
            )
            user.set_unusable_password()  # demo personas log in through /demo/login only
            user.save()
            return user

        cook_rows = [data.PERSONA_COOK, data.PERSONA_COOK2, *data.OTHER_COOKS]
        diner_rows = [data.PERSONA_DINER, *data.OTHER_DINERS]
        cooks = []
        for i, row in enumerate(cook_rows):
            user = make_user(row, 60 + i)
            cooks.append(
                CookProfile.objects.create(
                    user=user, bio=data.COOK_BIOS[i], food_safety_ack_at=now - timedelta(days=60 + i)
                )
            )
        diners = [make_user(row, 30 + i) for i, row in enumerate(diner_rows)]

        menus: dict[int, dict[str, list[MenuItem]]] = {}
        for i, cook in enumerate(cooks):
            menus[i] = {}
            for (meal, course), dishes in data.DISHES.items():
                name, description, ingredients, allergens, tags = dishes[i]
                item = MenuItem.objects.create(
                    cook=cook,
                    name=name,
                    description=description,
                    ingredients=ingredients,
                    meal_type=meal,
                    course=course,
                    allergens=allergens,
                    dietary_tags=tags,
                    is_specialty=(course == "main"),
                    allergens_confirmed_at=now - timedelta(days=20),
                )
                menus[i].setdefault(meal, []).append(item)

        def serve_time(when) -> datetime:
            kind, amount, hour = when
            if kind == "hours":
                return (now + timedelta(hours=amount)).replace(minute=0, second=0, microsecond=0)
            day = timezone.localdate(now, TZ) + timedelta(days=amount)
            return datetime.combine(day, time(hour), tzinfo=TZ)

        need_labels = iter(data.BRING_LIST_ITEMS * 3)
        custom_terms = iter(CUSTOM_TERMS * 4)
        completed: list[Booking] = []
        booking_count = 0
        for spec in OFFERINGS:
            serve_at = serve_time(spec.when)
            offering = Offering.objects.create(
                cook=cooks[spec.cook],
                title=spec.title,
                meal_type=spec.meal,
                serve_at=serve_at,
                booking_cutoff_at=serve_at - timedelta(hours=2),
                capacity=spec.capacity,
                fulfillment=spec.fulfillment,
                status=spec.status,
                pickup_note="Lobby of North Hall (Demo). Message the cook on arrival.",
                grocery_estimate_cents=spec.estimate,
                share_per_seat_cents=spec.share,
            )
            OfferingItem.objects.bulk_create(
                OfferingItem(offering=offering, item=it) for it in menus[spec.cook][spec.meal]
            )
            needs = [OfferingNeed.objects.create(offering=offering, label=next(need_labels)) for _ in range(spec.needs)]
            open_needs = list(needs)
            for diner_idx, seats, status, contribution, cancelled_by in spec.bookings:
                share_cents = 0
                terms = ""
                if contribution == "share":
                    share_cents = seats * spec.share
                elif contribution == "custom":
                    terms = next(custom_terms)
                    share_cents = min(200 * seats, seats * (spec.estimate // spec.capacity))
                decided = serve_at - timedelta(days=1) if status in (K, D, C) else None
                closed = (
                    serve_at + timedelta(hours=2)
                    if status == C
                    else (serve_at - timedelta(days=1) if status == X else None)
                )
                booking = Booking.objects.create(
                    offering=offering,
                    diner=diners[diner_idx],
                    seats=seats,
                    status=status,
                    allergen_ack_at=serve_at - timedelta(days=2),
                    contribution=contribution,
                    share_cents=share_cents,
                    terms=terms,
                    decided_at=decided,
                    closed_at=closed,
                    cancelled_by=cancelled_by,
                    contribution_received_at=closed if status == C and contribution != "none" else None,
                )
                booking_count += 1
                if contribution == "ingredients" and open_needs and status in (R, K, C):
                    need = open_needs.pop(0)
                    need.claimed_by_booking = booking
                    need.save(update_fields=["claimed_by_booking"])
                if status == C:
                    completed.append(booking)

        for i, booking in enumerate(completed):
            Review.objects.create(
                booking=booking,
                rating=rng.choice([3, 4, 4, 5, 5]),
                the_good=data.REVIEW_GOOD[i % len(data.REVIEW_GOOD)],
                the_bad=data.REVIEW_BAD[i % len(data.REVIEW_BAD)],
                hidden_at=now if i == len(completed) - 1 else None,
            )

        return {
            "campuses": len(campuses),
            "cooks": len(cooks),
            "diners": len(diners),
            "menu_items": MenuItem.objects.count(),
            "offerings": Offering.objects.count(),
            "bookings": booking_count,
            "reviews": len(completed),
        }
