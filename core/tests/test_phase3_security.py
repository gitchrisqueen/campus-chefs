import pytest

from core import seed_data
from tests import factories as f

BANNER = b'role="region" aria-label="Demo notice"'


@pytest.fixture
def demo_cook(db):
    # Seeded personas have unusable passwords (plan 2.4); password=None gives one.
    email, first, last, _, _ = seed_data.PERSONA_COOK
    return f.user(first=first, last=last, email=email, password=None)


@pytest.mark.django_db
def test_sec_03_demo_mode_on_shows_banner_and_demo_login_works(client, settings, demo_cook):
    settings.CC_DEMO_MODE = True
    home = client.get("/").content
    assert BANNER in home
    assert b"Try as demo cook" in home
    assert not demo_cook.has_usable_password()

    assert client.get("/demo/login/cook").status_code == 405
    assert client.post("/demo/login/nobody").status_code == 404
    assert client.post("/demo/login/diner").status_code == 404  # persona not seeded here
    response = client.post("/demo/login/cook")
    assert response.status_code == 302
    assert response["Location"] == "/me"
    assert int(client.session["_auth_user_id"]) == demo_cook.pk


@pytest.mark.django_db
def test_sec_03_demo_mode_off_hides_banner_and_demo_login_but_keeps_safety(client, settings, demo_cook):
    settings.CC_DEMO_MODE = False
    home = client.get("/")
    assert BANNER not in home.content
    assert b"Try as demo" not in home.content
    assert b'<meta name="robots" content="noindex, nofollow">' in home.content
    assert client.post("/demo/login/cook").status_code == 404
    assert client.get("/demo/login/cook").status_code == 404
    assert "_auth_user_id" not in client.session

    safety = client.get("/safety")
    assert safety.status_code == 200
    assert b"Nobody inspects the kitchens." in safety.content
    assert b'<meta name="robots" content="noindex, nofollow">' in safety.content


@pytest.mark.django_db
def test_sec_07_no_store_for_logged_in_users_only(client):
    anonymous = client.get("/")
    assert "no-store" not in anonymous.get("Cache-Control", "")

    client.force_login(f.user())
    for path in ["/", "/me", "/me/edit", "/safety"]:
        cache_control = client.get(path)["Cache-Control"]
        assert "private" in cache_control and "no-store" in cache_control, path
