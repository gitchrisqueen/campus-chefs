import pytest
from django.test import Client

from accounts.models import User
from bookings.models import Review
from meals.models import OfferingNeed
from tests import factories as f

PASSWORD = "a-long-test-password-1"


@pytest.fixture
def diner(db):
    return f.user(first="Ava", last="Reyes", email="ava.r@larkspur.example", password=PASSWORD)


@pytest.mark.django_db
def test_leg_02a_me_shows_own_profile_and_empty_bookings(client, diner):
    """Phase 3 part of LEG-02 (2008 `cook_main.php` hardcoded userID = 1); phase 6 adds the bookings."""
    f.user(first="Bruno", last="Quist", email="bruno.q@larkspur.example")
    client.force_login(diner)
    page = client.get("/me").content.decode()
    assert "Ava Reyes" in page and "Ava R." in page
    assert "Larkspur State University (Demo)" in page
    assert "My bookings" in page and "No bookings yet." in page
    assert "Cook and diner" not in page
    assert "Bruno" not in page and "bruno.q@" not in page

    f.cook(first="Marcus", email="marcus@larkspur.example", password=PASSWORD)
    client.login(username="marcus@larkspur.example", password=PASSWORD)
    assert "Cook and diner" in client.get("/me").content.decode()


@pytest.mark.django_db
def test_acct_01_delete_cancels_bookings_anonymizes_and_keeps_reviews(client, diner):
    cook = f.cook(first="Marcus", email="marcus@larkspur.example")
    upcoming = f.booking(f.offering(cook), diner, status="requested", contribution="ingredients")
    need = OfferingNeed.objects.create(offering=upcoming.offering, label="1 lb spaghetti", claimed_by_booking=upcoming)
    past = f.booking(f.offering(cook, days_ahead=-3, title="Past Dinner"), diner, status="completed")
    review = Review.objects.create(booking=past, rating=5, the_good="Great pancakes")
    other_session = Client()
    other_session.force_login(diner)
    client.force_login(diner)

    assert client.get("/me/delete").status_code == 200
    response = client.post("/me/delete", {"password": PASSWORD})
    assert response.status_code == 302
    assert response["Location"] == "/"
    assert "_auth_user_id" not in client.session

    upcoming.refresh_from_db()
    assert (upcoming.status, upcoming.cancelled_by) == ("cancelled", "diner")
    assert upcoming.closed_at is not None
    need.refresh_from_db()
    assert need.claimed_by_booking is None
    past.refresh_from_db()
    assert past.status == "completed"

    diner.refresh_from_db()
    assert not diner.is_active
    assert diner.email == f"deleted-{diner.pk}@invalid.example"
    assert not diner.has_usable_password()
    assert "Ava" not in diner.first_name and diner.last_name == ""
    review.refresh_from_db()
    assert review.booking.diner.public_name == "Former student"
    assert other_session.get("/me").status_code == 302
    assert client.post("/login", {"username": "ava.r@larkspur.example", "password": PASSWORD}).status_code == 200


@pytest.mark.django_db
def test_acct_02_delete_with_wrong_password_changes_nothing(client, diner):
    booking = f.booking(f.offering(f.cook()), diner, status="requested")
    client.force_login(diner)
    response = client.post("/me/delete", {"password": "wrong-password-123"})
    assert response.status_code == 200
    assert b"Your password is incorrect." in response.content

    diner.refresh_from_db()
    booking.refresh_from_db()
    assert diner.is_active and diner.email == "ava.r@larkspur.example"
    assert diner.check_password(PASSWORD)
    assert booking.status == "requested"
    assert client.get("/me").status_code == 200


def _edit_data(user, **overrides):
    data = {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "campus": user.campus_id,
        "classification": "",
        "current_password": "",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_acct_04_email_change_needs_current_password(client, diner):
    client.force_login(diner)
    assert client.get("/me/edit").status_code == 200

    rejected = client.post("/me/edit", _edit_data(diner, email="ava.new@larkspur.example"))
    assert rejected.status_code == 200
    assert b"Enter your current password to change your email." in rejected.content
    diner.refresh_from_db()
    assert diner.email == "ava.r@larkspur.example"

    wrong = client.post(
        "/me/edit", _edit_data(diner, email="ava.new@larkspur.example", current_password="wrong-password-123")
    )
    assert wrong.status_code == 200
    diner.refresh_from_db()
    assert diner.email == "ava.r@larkspur.example"

    accepted = client.post("/me/edit", _edit_data(diner, email="ava.new@larkspur.example", current_password=PASSWORD))
    assert accepted.status_code == 302
    assert accepted["Location"] == "/me"
    diner.refresh_from_db()
    assert diner.email == "ava.new@larkspur.example"


@pytest.mark.django_db
def test_acct_04_name_change_needs_no_password_but_email_must_be_free(client, diner):
    f.user(email="taken@larkspur.example")
    client.force_login(diner)
    assert client.post("/me/edit", _edit_data(diner, first_name="Avery")).status_code == 302
    diner.refresh_from_db()
    assert diner.first_name == "Avery"

    taken = client.post("/me/edit", _edit_data(diner, email="TAKEN@larkspur.example", current_password=PASSWORD))
    assert taken.status_code == 200
    assert b"already registered" in taken.content
    assert User.objects.get(pk=diner.pk).email == "ava.r@larkspur.example"
