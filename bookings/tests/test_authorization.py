"""AZ-03, AZ-04, AZ-05: who may see and change a booking (plan 3.3, 5.2)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import User
from accounts.tests.test_account import _edit_data
from accounts.tests.test_registration import _data as registration_data
from bookings.models import Booking, Review
from meals.models import MenuItem, Offering
from meals.tests.test_kitchen import item_data, offering_data
from tests import factories as f

S = Booking.Status


@pytest.mark.django_db
def test_az_03_unrelated_user_gets_404_on_a_booking(client, offering, diner):
    booking = f.booking(offering, diner, status=S.REQUESTED)
    client.force_login(f.user(first="Sam", last="Turner"))
    assert client.get(f"/bookings/{booking.pk}").status_code == 404
    assert client.post(f"/bookings/{booking.pk}/transition", {"to": "cancelled"}).status_code == 404
    booking.refresh_from_db()
    assert booking.status == S.REQUESTED
    for participant in (diner, offering.cook.user):
        client.force_login(participant)
        assert client.get(f"/bookings/{booking.pk}").status_code == 200


@pytest.mark.django_db
def test_az_04_diner_cannot_mark_own_booking_completed(client, offering, diner):
    booking = f.booking(offering, diner, status=S.CONFIRMED)
    client.force_login(diner)
    response = client.post(f"/bookings/{booking.pk}/transition", {"to": "completed"})
    assert response.status_code == 403
    booking.refresh_from_db()
    assert booking.status == S.CONFIRMED and booking.closed_at is None


@pytest.mark.django_db
def test_az_05_anonymous_posts_to_kitchen_and_booking_routes_go_to_login(client, offering, diner):
    item = offering.items.get()
    booking = f.booking(offering, diner, status=S.CONFIRMED, contribution="share", share_cents=400)
    routes = [
        "/kitchen/setup",
        "/kitchen/bio",
        "/kitchen/items/new",
        f"/kitchen/items/{item.pk}/edit",
        f"/kitchen/items/{item.pk}/archive",
        "/kitchen/offerings/new",
        f"/kitchen/offerings/{offering.pk}/edit",
        f"/kitchen/offerings/{offering.pk}/cancel",
        f"/kitchen/offerings/{offering.pk}/delete",
        f"/bookings/{booking.pk}",
        f"/bookings/{booking.pk}/transition",
        f"/bookings/{booking.pk}/received",
    ]
    for route in routes:
        response = client.post(route, {"to": "cancelled", "name": "Changed", "title": "Changed"})
        assert response.status_code == 302, route
        assert response["Location"].startswith("/login?next="), route

    booking.refresh_from_db()
    offering.refresh_from_db()
    item.refresh_from_db()
    assert (booking.status, booking.contribution_received_at) == (S.CONFIRMED, None)
    assert (offering.status, offering.title) == (Offering.Status.OPEN, "Pancake Breakfast")
    assert (item.is_active, item.name) == (True, "Buttermilk Pancakes")
    assert MenuItem.objects.count() == 1 and Offering.objects.count() == 1


@pytest.mark.django_db
def test_booking_page_shows_timeline_and_the_actions_each_side_may_take(client, offering, diner):
    """Supporting test: the timeline and the action buttons follow the state machine."""
    booking = f.booking(offering, diner, status=S.REQUESTED, contribution="share", share_cents=400)
    client.force_login(offering.cook.user)
    html = client.get(f"/bookings/{booking.pk}").content.decode()
    assert "Requested" in html and ">Confirm<" in html and ">Decline<" in html and "Cancel booking" in html
    assert "Ava R. asked for 1 seat" in html

    client.post(f"/bookings/{booking.pk}/transition", {"to": "confirmed"})
    client.force_login(diner)
    html = client.get(f"/bookings/{booking.pk}").content.decode()
    assert "Confirmed" in html and "Cancel booking" in html and ">Confirm<" not in html
    assert "Lobby of North Hall (Demo)." in html

    client.post(f"/bookings/{booking.pk}/transition", {"to": "cancelled"})
    html = client.get(f"/bookings/{booking.pk}").content.decode()
    assert "Cancelled by diner" in html and "Cancel booking" not in html
    assert "Grocery share: $4.00" in html and "pay the cook in person" not in html


@pytest.mark.django_db
def test_booking_page_marks_completed_and_expired(client, cook, diner):
    """Supporting test: a past confirmed booking can be completed; a past request reads "Expired"."""
    past = f.offering(cook, days_ahead=-1)
    confirmed = f.booking(past, diner, status=S.CONFIRMED)
    client.force_login(cook.user)
    assert "Mark completed" in client.get(f"/bookings/{confirmed.pk}").content.decode()
    client.post(f"/bookings/{confirmed.pk}/transition", {"to": "completed"})
    html = client.get(f"/bookings/{confirmed.pk}").content.decode()
    assert "Completed" in html and "Mark completed" not in html

    stale = f.booking(f.offering(cook, days_ahead=-2), f.user(first="Sam"), status=S.REQUESTED)
    html = client.get(f"/bookings/{stale.pk}").content.decode()
    assert "Expired" in html and ">Confirm<" not in html
    assert client.post(f"/bookings/{stale.pk}/transition", {"to": "nonsense"}).status_code == 409


@pytest.mark.django_db
def test_az_08_extra_fields_on_every_form_change_nothing(client, offering, diner):
    """Registration, account, item, offering, booking and review forms ignore fields they do not list."""
    cook = offering.cook
    other = f.user(first="Sam", last="Turner")
    extra = {
        "is_staff": "on",
        "is_superuser": "on",
        "is_active": "off",
        "status": "completed",
        "hidden_at": "2026-01-01 00:00:00",
        "cook": other.pk,
        "diner": other.pk,
    }

    client.post("/register", {**registration_data(), **extra})
    new_user = User.objects.get(email="new.student@larkspur.example")
    assert (new_user.is_staff, new_user.is_superuser, new_user.is_active) == (False, False, True)

    client.force_login(diner)
    assert client.post("/me/edit", {**_edit_data(diner, first_name="Avery"), **extra}).status_code == 302
    diner.refresh_from_db()
    assert (diner.first_name, diner.is_staff, diner.is_superuser, diner.is_active) == ("Avery", False, False, True)

    client.force_login(cook.user)
    new_item = {**item_data(name="Hash Browns", meal_type="breakfast"), **extra}
    assert client.post("/kitchen/items/new", new_item).status_code == 302
    item = cook.menu_items.get(name="Hash Browns")
    assert item.cook == cook and item.is_active
    new_offering = {**offering_data([item], title="Brunch Plate"), **extra}
    assert client.post("/kitchen/offerings/new", new_offering).status_code == 302
    brunch = Offering.objects.get(title="Brunch Plate")
    assert (brunch.cook, brunch.status) == (cook, Offering.Status.OPEN)

    client.force_login(diner)
    book = {"seats": "1", "contribution": "share", "allergen_ack": "on", **extra}
    assert client.post(f"/offerings/{offering.pk}/book", book).status_code == 303
    booking = Booking.objects.get(offering=offering)
    assert (booking.diner, booking.status) == (diner, S.REQUESTED)

    booking.status, booking.closed_at = S.COMPLETED, timezone.now() - timedelta(days=1)
    booking.save()
    assert client.post(f"/bookings/{booking.pk}/review", {"rating": "4", **extra}).status_code == 303
    review = Review.objects.get()
    assert (review.booking, review.hidden_at, review.rating) == (booking, None, 4)
    booking.refresh_from_db()
    assert booking.status == S.COMPLETED and booking.diner == diner
