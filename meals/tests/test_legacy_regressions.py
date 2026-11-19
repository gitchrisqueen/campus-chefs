"""Regression tests for the 2008 cook-page defects (plan 1.3 #10 and #13, plan 12).

Written before the phase 4 code that makes them pass.
"""

import re

import pytest

from tests import factories as f


@pytest.mark.django_db
def test_leg_01_cook_page_has_no_gender_or_age_and_unique_dt_labels(client):
    """2008 `cook_main.php:39-40` printed the age under a "Gender:" label."""
    cook = f.cook(first="Marcus", last="Bell", classification="senior")
    f.menu_item(cook, "Baked Potato", meal_type="dinner", course="side")
    f.menu_item(cook, "French Toast", is_specialty=True)
    f.offering(cook)

    response = client.get(f"/cooks/{cook.pk}")
    assert response.status_code == 200
    html = response.content.decode()
    assert not re.search(r"\b(Gender|Age)\b", html)
    labels = re.findall(r"<dt[^>]*>(.*?)</dt>", html, re.S)
    assert labels, "the cook page lists its facts in a <dl>"
    labels = [label.strip() for label in labels]
    assert len(labels) == len(set(labels)), labels


@pytest.mark.django_db
def test_leg_03_me_shows_kitchen_panel_only_for_cooks(client):
    """2008 `profile.php:8` hardcoded `$profile_type = "cook"` for every user."""
    diner = f.user(first="Jordan", last="Kim")
    client.force_login(diner)
    html = client.get("/me").content.decode()
    assert 'id="kitchen-panel"' not in html
    assert "My kitchen" not in html
    assert 'href="/kitchen/setup"' in html, "a diner can still choose to start cooking"

    cook = f.cook(first="Marcus", last="Bell")
    f.offering(cook, title="Pancake Breakfast")
    client.force_login(cook.user)
    html = client.get("/me").content.decode()
    assert 'id="kitchen-panel"' in html
    assert "My kitchen" in html
    assert "Pancake Breakfast" in html
