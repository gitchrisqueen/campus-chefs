"""Phase 4 public pages: /cooks/<id> and the read-only /offerings/<id>. No plan ID; they cover the views."""

import pytest
from django.utils import timezone

from bookings.models import Review
from meals.models import OfferingNeed
from tests import factories as f


@pytest.fixture
def cook(db):
    profile = f.cook(first="Marcus", last="Bell", email="marcus.b@larkspur.example")
    profile.bio = "Pancakes are my thing."
    profile.save()
    return profile


@pytest.mark.django_db
def test_cook_page_shows_specialties_menu_offerings_and_visible_reviews(client, cook):
    pancakes = f.menu_item(cook, "Buttermilk Pancakes", is_specialty=True, allergens=["wheat", "milk"])
    f.menu_item(cook, "Steak Frites", meal_type="dinner", is_specialty=True, dietary_tags=["gluten_free"])
    f.menu_item(cook, "Old Waffles", is_active=False)
    upcoming = f.offering(cook, title="Pancake Breakfast")
    upcoming.items.add(pancakes)
    f.offering(cook, title="Cancelled Brunch", status="cancelled")
    past = f.offering(cook, title="Last Week Brunch", days_ahead=-7)
    diner = f.user(first="Jordan", last="Kim")
    Review.objects.create(booking=f.booking(past, diner, status="completed"), rating=4, the_good="Fluffy.")
    other = f.user(first="Sam", last="Turner")
    Review.objects.create(
        booking=f.booking(past, other, status="completed"), rating=1, the_bad="Hidden one.", hidden_at=timezone.now()
    )

    html = client.get(f"/cooks/{cook.pk}").content.decode()
    specialties = html[html.index('id="specialties-heading"') : html.index('id="menu-heading"')]
    assert specialties.index("Buttermilk Pancakes") < specialties.index("Steak Frites"), "breakfast before dinner"
    assert "Pancakes are my thing." in html
    assert "Contains: wheat, milk" in html and "Gluten-free" in html
    assert "Pancake Breakfast" in html and "$4.00 grocery share per seat" in html
    assert "Cancelled Brunch" not in html and "Old Waffles" not in html
    assert "4.0 out of 5 (1 review)" in html
    assert "The good:</strong> Fluffy." in html and "Jordan K." in html
    assert "Hidden one." not in html


@pytest.mark.django_db
def test_cook_page_404_for_inactive_or_missing_cook(client, cook):
    assert client.get("/cooks/999999").status_code == 404
    cook.user.is_active = False
    cook.user.save()
    assert client.get(f"/cooks/{cook.pk}").status_code == 404


@pytest.mark.django_db
def test_offering_page_shows_dishes_chip_in_and_hides_pickup_note_from_guests(client, cook):
    item = f.menu_item(cook, "Buttermilk Pancakes", allergens=["egg"])
    offering = f.offering(cook, title="Pancake Breakfast", pickup_note="Lobby of North Hall (Demo).", capacity=4)
    offering.items.add(item)
    OfferingNeed.objects.create(offering=offering, label="1 lb spaghetti")
    taken = OfferingNeed.objects.create(offering=offering, label="1 dozen eggs")
    requested = f.user(first="Sam", last="Turner")
    taken.claimed_by_booking = f.booking(offering, requested, seats=2, contribution="ingredients")
    taken.save()

    html = client.get(f"/offerings/{offering.pk}").content.decode()
    for text in (
        "Pancake Breakfast",
        "Buttermilk Pancakes",
        "Contains: egg",
        "$4.00 grocery share per seat",
        "or bring an item",
        "1 lb spaghetti",
        "(taken)",
        "2 of 4",
        "not a safety guarantee",
        'id="booking-panel"',
    ):
        assert text in html, text
    assert "Lobby of North Hall" not in html

    client.force_login(requested)
    assert "Lobby of North Hall" not in client.get(f"/offerings/{offering.pk}").content.decode()

    confirmed = f.user(first="Nia", last="Johnson")
    f.booking(offering, confirmed, status="confirmed")
    client.force_login(confirmed)
    assert "Lobby of North Hall" in client.get(f"/offerings/{offering.pk}").content.decode()

    client.force_login(cook.user)
    html = client.get(f"/offerings/{offering.pk}").content.decode()
    assert "Lobby of North Hall" in html and "Edit this meal" in html


@pytest.mark.django_db
def test_free_and_bring_only_offerings_and_cancelled_notice(client, cook):
    free = f.offering(cook, title="Soup Lunch", grocery_estimate_cents=0, share_per_seat_cents=0)
    html = client.get(f"/offerings/{free.pk}").content.decode()
    assert ">Free<" in html and "Nothing to chip in" in html

    bring = f.offering(cook, title="Pasta Night", share_per_seat_cents=0, status="cancelled")
    OfferingNeed.objects.create(offering=bring, label="1 lb spaghetti")
    html = client.get(f"/offerings/{bring.pk}").content.decode()
    assert "Bring an item" in html and "The cook cancelled this meal." in html

    cook.user.is_active = False
    cook.user.save()
    assert client.get(f"/offerings/{free.pk}").status_code == 404
