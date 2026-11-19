"""Regression tests for the 2008 auth and registration defects (plan 1.3, 12).

Written before the phase 3 code that makes them pass.
"""

import pytest

from accounts.models import User
from meals.models import CookProfile
from tests import factories as f

PASSWORD = "test-only-long-password-1"


def _register(client, **overrides):
    data = {
        "email": "new.student@larkspur.example",
        "first_name": "Rory",
        "last_name": "Vance",
        "campus": f.campus().pk,
        "password1": PASSWORD,
        "password2": PASSWORD,
        "adult": "on",
        "role": "eat",
    }
    data.update(overrides)
    return client.post("/register", {k: v for k, v in data.items() if v is not None})


@pytest.mark.django_db
@pytest.mark.parametrize("login_as", ["Ava", "' OR 1=1 -- ", "ava.r@larkspur.example' OR '1'='1"])
def test_auth_07_sqli_login_bypass_rejected(client, login_as):
    """2008 `src/sqlQueries.php` built the login query by string concatenation."""
    f.user(first="Ava", email="ava.r@larkspur.example", password=PASSWORD)
    response = client.post("/login", {"username": login_as, "password": PASSWORD})
    assert response.status_code == 200
    assert b"Email or password is incorrect" in response.content
    assert "_auth_user_id" not in client.session

    # Also with the SQL fragment in the password field.
    response = client.post("/login", {"username": "ava.r@larkspur.example", "password": "' OR 1=1 -- "})
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_leg_04_registration_keeps_chosen_campus_and_cook_role(client):
    """2008 registration dropped the campus and role the student picked."""
    cobalt = f.campus("cobalt-bay", "Cobalt Bay Institute (Demo)")
    f.campus()  # a second campus, so the choice matters
    response = _register(client, campus=cobalt.pk, role="cook", food_safety="on")
    assert response.status_code == 302, response.content.decode()
    user = User.objects.get(email="new.student@larkspur.example")
    assert user.campus.slug == "cobalt-bay"
    assert CookProfile.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_leg_05_password_with_html_and_quote_characters_round_trips(client):
    """2008 code passed the raw password through GET and string-built SQL."""
    tricky = "a&b<c>\"d'e-1234"
    response = _register(client, password1=tricky, password2=tricky)
    assert response.status_code == 302, response.content.decode()
    client.post("/logout")
    assert "_auth_user_id" not in client.session

    response = client.post("/login", {"username": "new.student@larkspur.example", "password": tricky})
    assert response.status_code == 302
    assert response["Location"] == "/me"
    assert int(client.session["_auth_user_id"]) == User.objects.get(email="new.student@larkspur.example").pk
