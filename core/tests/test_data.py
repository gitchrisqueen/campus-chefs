import re
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from accounts.models import User
from bookings.models import Booking, Review
from meals.models import Campus, MenuItem, Offering
from tests import factories as f


@pytest.mark.django_db
def test_data_01_seed_uses_only_example_emails_and_demo_campuses():
    call_command("seed_demo")
    assert User.objects.exists()
    assert all(email.endswith(".example") for email in User.objects.values_list("email", flat=True))
    assert all(name.endswith("(Demo)") for name in Campus.objects.values_list("name", flat=True))


@pytest.mark.django_db
def test_data_01_seed_shape_matches_plan():
    call_command("seed_demo")
    assert Campus.objects.count() == 3
    assert User.objects.filter(cook_profile__isnull=False).count() == 8
    assert User.objects.filter(cook_profile__isnull=True).count() == 14
    assert MenuItem.objects.count() == 48
    assert Offering.objects.count() == 16
    assert Review.objects.count() == 12
    assert Review.objects.filter(hidden_at__isnull=False).count() == 1
    assert set(Booking.objects.values_list("status", flat=True)) == {s for s, _ in Booking.Status.choices}
    assert set(Booking.objects.values_list("contribution", flat=True)) == {c for c, _ in Booking.Contribution.choices}
    for name in ["Baked Potato", "Macaroni and Cheese", "Collard Greens", "French Toast"]:
        assert MenuItem.objects.filter(name=name).exists(), name

    now = timezone.now()
    offerings = Offering.objects.all()
    assert any(o.serve_at < now for o in offerings)
    assert any(o.serve_at > now + timedelta(days=1) for o in offerings)
    kinds = {(o.share_per_seat_cents > 0, o.needs.exists()) for o in offerings}
    assert kinds == {(False, False), (True, False), (False, True), (True, True)}, "free, share, bring list, both"

    # E2E-02 fixture: the demo diner's confirmed booking on the demo cook's meal served yesterday.
    demo = Booking.objects.get(
        diner__email="diner@larkspur.example", offering__cook__user__email="cook@larkspur.example", status="confirmed"
    )
    assert demo.offering.serve_at < now
    assert demo.share_cents == 400 and demo.contribution_received_at is None
    # E2E-01 fixture: a future pancake breakfast by the demo cook that the demo diner has not booked.
    pancakes = Offering.objects.get(
        cook__user__email="cook@larkspur.example", serve_at__gt=now, items__name="Buttermilk Pancakes"
    )
    assert not pancakes.bookings.filter(diner__email="diner@larkspur.example").exists()


@pytest.mark.django_db
def test_data_01_seed_if_empty_and_reset(settings):
    call_command("seed_demo")
    call_command("seed_demo", if_empty=True)
    assert Offering.objects.count() == 16
    settings.CC_DEMO_MODE = True
    call_command("seed_demo", reset=True)
    assert Offering.objects.count() == 16
    settings.CC_DEMO_MODE = False
    with pytest.raises(Exception, match="CC_DEMO_MODE"):
        call_command("seed_demo", reset=True)


@pytest.mark.django_db
def test_data_02_no_payment_columns_only_grocery_cents():
    banned = re.compile(r"card|iban|routing|account_number|payout|tip|venmo|cashapp|paypal|handle")
    money = re.compile(r"cents|price|amount|cost")
    money_columns = set()
    with connection.cursor() as cursor:
        for table in connection.introspection.table_names(cursor):
            for column in connection.introspection.get_table_description(cursor, table):
                name = column.name
                assert not banned.search(name), f"{table}.{name}"
                if money.search(name):
                    money_columns.add(name)
    assert money_columns == {"grocery_estimate_cents", "share_per_seat_cents", "share_cents"}


def _offering(**extra):
    return f.offering(f.cook(), **extra)


def _two_specialties():
    cook = f.cook()
    f.menu_item(cook, "Pancakes", is_specialty=True)
    f.menu_item(cook, "Waffles", is_specialty=True)


def _duplicate_active_booking():
    offering, diner = _offering(), f.user()
    f.booking(offering, diner, status="requested")
    f.booking(offering, diner, status="confirmed")


DATA_03_CASES = {
    "no_profit_share_above_estimate": lambda: _offering(
        grocery_estimate_cents=2000, capacity=4, share_per_seat_cents=525
    ),
    "rating_0": lambda: Review.objects.create(booking=f.booking(_offering(), f.user(), status="completed"), rating=0),
    "seats_5": lambda: f.booking(_offering(), f.user(), seats=5),
    "capacity_13": lambda: _offering(capacity=13, share_per_seat_cents=0),
    "cutoff_after_serve": lambda: _offering(booking_cutoff_at=timezone.now() + timedelta(days=9)),
    "duplicate_active_booking": _duplicate_active_booking,
    "second_specialty": _two_specialties,
    "bad_enum_meal_type": lambda: f.menu_item(f.cook(), meal_type="brunch"),
    "cancelled_by_on_active_booking": lambda: f.booking(_offering(), f.user(), status="requested", cancelled_by="cook"),
    "custom_without_terms": lambda: f.booking(_offering(), f.user(), contribution="custom", terms=""),
    "share_cents_on_free_contribution": lambda: f.booking(_offering(), f.user(), contribution="none", share_cents=400),
    "bad_allergen": lambda: f.menu_item(f.cook(), allergens=["gluten"]),
}


@pytest.mark.django_db
@pytest.mark.parametrize("case", sorted(DATA_03_CASES))
def test_data_03_constraint_violations_raise_integrity_error(case):
    with pytest.raises(IntegrityError), transaction.atomic():
        DATA_03_CASES[case]()


@pytest.mark.django_db
def test_data_03_valid_rows_pass_the_same_constraints():
    offering = _offering(grocery_estimate_cents=2000, capacity=4, share_per_seat_cents=500)
    booking = f.booking(
        offering,
        f.user(),
        status="cancelled",
        cancelled_by="diner",
        contribution="custom",
        terms="I'll bring drinks",
        share_cents=300,
    )
    assert booking.pk and offering.pk


@pytest.mark.django_db
def test_data_01_reset_keeps_staff_and_their_campus(settings, monkeypatch):
    """Operator flow from docs/OPERATIONS.md: createsuperuser on a seeded campus, then reseed."""
    call_command("seed_demo")
    campus = Campus.objects.get(slug="larkspur")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "a-long-admin-password-42")
    call_command(
        "createsuperuser",
        interactive=False,
        email="admin@larkspur.example",
        first_name="Ada",
        last_name="Min",
        campus=campus.pk,
    )
    admin = User.objects.get(email="admin@larkspur.example")
    assert admin.is_superuser and admin.adult_attested_at is not None

    settings.CC_DEMO_MODE = True
    call_command("seed_demo", reset=True)
    assert User.objects.filter(email="admin@larkspur.example").exists()
    assert Campus.objects.count() == 3
    assert Offering.objects.count() == 16
    assert Review.objects.count() == 12


@pytest.mark.django_db(transaction=True)
def test_data_01_bootstrap_seeds_only_in_demo_mode(settings):
    settings.CC_DEMO_MODE = False
    call_command("bootstrap_demo")
    assert not Campus.objects.exists()
    settings.CC_DEMO_MODE = True
    call_command("bootstrap_demo")
    assert Offering.objects.count() == 16
