"""Phase 9 hardening: the search cache key, kitchen races, the redirect helper, audit logging and the review admin."""

import logging

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.utils import timezone

from accounts.models import User
from bookings.models import Booking, Review
from meals.forms import CookSetupForm, MenuItemForm
from meals.models import MenuItem, Offering
from meals.tests.test_kitchen import item_data, offering_data
from tests import factories as f

S = Booking.Status


@pytest.fixture
def cook(db):
    return f.cook(first="Marcus", last="Bell", email="marcus.b@larkspur.example")


@pytest.fixture
def diner(db):
    return f.user(first="Ava", last="Reyes", email="ava.r@larkspur.example")


@pytest.fixture
def offering(cook):
    meal = f.offering(cook, title="Pancake Breakfast")
    meal.items.add(f.menu_item(cook, "Buttermilk Pancakes", allergens=["egg"]))
    return meal


def messages_of(response):
    return [str(m) for m in response.context["messages"]]


# --- /search caches by header ------------------------------------------------------------


@pytest.mark.django_db
def test_search_response_varies_on_hx_request(client):
    full = client.get("/search")
    partial = client.get("/search", HTTP_HX_REQUEST="true")
    assert "HX-Request" in full["Vary"]
    assert "HX-Request" in partial["Vary"]
    assert full.templates[0].name != partial.templates[0].name


# --- kitchen races give a message, not a 500 ---------------------------------------------


@pytest.mark.django_db
def test_kitchen_setup_race_on_the_one_to_one_redirects(client, monkeypatch):
    user = f.user()
    client.force_login(user)

    def clash(self, *args, **kwargs):
        raise IntegrityError("duplicate key value violates unique constraint")

    monkeypatch.setattr(CookSetupForm, "save", clash)
    response = client.post("/kitchen/setup", {"bio": "", "food_safety": "on"})
    assert response.status_code == 302
    assert response["Location"] == "/kitchen"


@pytest.mark.django_db
def test_item_create_race_on_a_unique_constraint_shows_a_form_error(client, cook, monkeypatch):
    def clash(self, *args, **kwargs):
        raise IntegrityError("duplicate key value violates unique constraint")

    monkeypatch.setattr(MenuItemForm, "save", clash)
    client.force_login(cook.user)
    response = client.post("/kitchen/items/new", item_data())
    assert response.status_code == 200
    assert "Someone changed this at the same moment" in response.content.decode()
    assert MenuItem.objects.filter(cook=cook, name="Baked Potato").count() == 0


@pytest.mark.django_db
def test_offering_delete_race_on_a_protected_booking_shows_a_message(client, offering, monkeypatch):
    def protected(self, *args, **kwargs):
        raise ProtectedError("protected", [])

    monkeypatch.setattr(Offering, "delete", protected)
    client.force_login(offering.cook.user)
    response = client.post(f"/kitchen/offerings/{offering.pk}/delete", follow=True)
    assert response.status_code == 200
    assert any("has bookings" in m for m in messages_of(response))
    assert Offering.objects.filter(pk=offering.pk).exists()


# --- the booking redirect helper honours the scheme --------------------------------------


@pytest.mark.django_db
def test_back_helper_rejects_an_http_next_on_a_secure_request(client, offering, diner):
    booking = f.booking(offering, diner, status=S.REQUESTED)
    client.force_login(diner)
    response = client.post(
        f"/bookings/{booking.pk}/transition", {"to": "cancelled", "next": "http://testserver/search"}, secure=True
    )
    assert response.status_code == 303
    assert response["Location"] == booking.get_absolute_url()


@pytest.mark.django_db
def test_back_helper_keeps_a_same_host_path(client, offering, diner):
    booking = f.booking(offering, diner, status=S.REQUESTED)
    client.force_login(diner)
    response = client.post(f"/bookings/{booking.pk}/transition", {"to": "cancelled", "next": "/me"}, secure=True)
    assert response["Location"] == "/me"


# --- audit logging: ids only -------------------------------------------------------------


def lines(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]


@pytest.mark.django_db
def test_booking_transitions_are_logged_with_ids_only(client, offering, diner, caplog):
    client.force_login(diner)
    with caplog.at_level(logging.INFO):
        client.post(f"/offerings/{offering.pk}/book", {"seats": "1", "contribution": "share", "allergen_ack": "on"})
        booking = Booking.objects.get()
        client.force_login(offering.cook.user)
        client.post(f"/bookings/{booking.pk}/transition", {"to": "confirmed"})
    text = "\n".join(lines(caplog))
    assert f"booking {booking.pk}: requested" in text
    assert f"booking {booking.pk}: requested -> confirmed by cook" in text
    for private in ("Ava", "Reyes", "Marcus", "larkspur.example"):
        assert private not in text


@pytest.mark.django_db
def test_kitchen_mutations_are_logged_with_ids_only(client, cook, caplog):
    client.force_login(cook.user)
    with caplog.at_level(logging.INFO):
        client.post("/kitchen/items/new", item_data(name="Secret Sauce Surprise"))
        item = MenuItem.objects.get(name="Secret Sauce Surprise")
        client.post(f"/kitchen/items/{item.pk}/edit", item_data(name="Secret Sauce Surprise"))
        client.post(f"/kitchen/items/{item.pk}/archive")
        meal = f.offering(cook, title="Private Supper Club")
        client.post(f"/kitchen/offerings/{meal.pk}/cancel")
        gone = f.offering(cook, title="Another Supper Club", days_ahead=3)
        client.post(f"/kitchen/offerings/{gone.pk}/delete")
    text = "\n".join(lines(caplog))
    events = ("menu item created", "menu item edited", "menu item archived", "offering cancelled", "offering deleted")
    for event in events:
        assert event in text
    for private in ("Secret Sauce", "Supper Club", "Marcus", "larkspur.example"):
        assert private not in text


@pytest.mark.django_db
def test_offering_create_and_edit_are_logged(client, cook, caplog):
    item = f.menu_item(cook, "Pancakes")
    client.force_login(cook.user)
    with caplog.at_level(logging.INFO):
        client.post("/kitchen/offerings/new", offering_data([item]))
        meal = Offering.objects.get()
        client.post(f"/kitchen/offerings/{meal.pk}/edit", offering_data([item], title="Renamed Brunch"))
    text = "\n".join(lines(caplog))
    assert f"offering created: cook {cook.pk} offering {meal.pk}" in text
    assert f"offering edited: cook {cook.pk} offering {meal.pk}" in text
    assert "Renamed Brunch" not in text


@pytest.mark.django_db
def test_account_deletion_is_logged_by_id_only(client, diner, caplog):
    diner.set_password("a-long-test-password-1")
    diner.save()
    client.force_login(diner)
    with caplog.at_level(logging.INFO):
        response = client.post("/me/delete", {"password": "a-long-test-password-1"})
    assert response.status_code == 302
    text = "\n".join(lines(caplog))
    assert f"account deleted: user {diner.pk}" in text
    assert "ava.r@" not in text


# --- the review admin ---------------------------------------------------------------------


@pytest.fixture
def staff(db):
    return f.user(first="Staff", last="Person", is_staff=True, is_superuser=True)


@pytest.fixture
def review(offering, diner):
    done = f.booking(offering, diner, status=S.COMPLETED, closed_at=timezone.now())
    return Review.objects.create(booking=done, rating=2, the_bad="Cold.")


@pytest.mark.django_db
def test_hide_action_writes_a_log_entry_a_message_and_an_audit_line(client, staff, review, caplog):
    client.force_login(staff)
    with caplog.at_level(logging.INFO):
        response = client.post(
            "/admin/bookings/review/", {"action": "hide_reviews", "_selected_action": [review.pk]}, follow=True
        )
    review.refresh_from_db()
    assert review.hidden_at is not None
    entry = LogEntry.objects.get(object_id=str(review.pk))
    assert entry.action_flag == CHANGE
    assert entry.user_id == staff.pk
    assert "Hid 1 review." in response.content.decode()
    assert f"review hidden: review {review.pk} by staff {staff.pk}" in "\n".join(lines(caplog))


@pytest.mark.django_db
def test_review_admin_shows_booking_and_rating_read_only(client, staff, review):
    client.force_login(staff)
    page = client.get(f"/admin/bookings/review/{review.pk}/change/")
    assert page.status_code == 200
    assert 'name="rating"' not in page.content.decode()
    assert 'name="booking"' not in page.content.decode()
    assert 'name="hidden_at_0"' in page.content.decode()
    assert User.objects.filter(pk=staff.pk).exists()
