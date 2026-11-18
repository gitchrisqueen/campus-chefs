"""Phase 4: the kitchen (cook setup, menu and offering CRUD), its permissions and the money rules."""

import re
from datetime import timedelta

import pytest
from django.apps import apps
from django.db import IntegrityError, models, transaction
from django.template import Context, Template
from django.utils import timezone

from meals.forms import NO_PROFIT, MenuItemForm, OfferingForm
from meals.models import CookProfile, MenuItem, Offering, OfferingNeed
from meals.money import format_cents, suggested_share_cents
from tests import factories as f


def item_data(**overrides):
    data = {
        "name": "Baked Potato",
        "meal_type": "dinner",
        "course": "side",
        "description": "Crispy skin, butter and chives.",
        "ingredients": "Potatoes, butter, chives, potatoes",
        "allergens": ["milk"],
        "dietary_tags": ["vegetarian", "gluten_free"],
        "allergens_complete": "on",
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


def offering_data(items, **overrides):
    serve_at = timezone.localtime() + timedelta(days=3)
    data = {
        "title": "Pancake Breakfast",
        "meal_type": "breakfast",
        "items": [i.pk for i in items],
        "serve_at": serve_at.strftime("%Y-%m-%dT%H:%M"),
        "booking_cutoff_at": (serve_at - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
        "capacity": "4",
        "fulfillment": "pickup",
        "pickup_note": "Lobby of North Hall (Demo).",
        "grocery_estimate": "20.00",
        "share_per_seat": "4.00",
        "bring_list": "1 lb spaghetti\n\n1 dozen eggs\n",
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


@pytest.fixture
def cook(db):
    return f.cook(first="Marcus", last="Bell", email="marcus.b@larkspur.example")


@pytest.fixture
def other_cook(db):
    return f.cook(first="Elena", last="Ortiz", email="elena.o@larkspur.example")


# --- AZ: authorization ------------------------------------------------------------------


@pytest.mark.django_db
def test_az_01_diner_without_cook_profile_gets_403_on_kitchen_routes(client):
    diner = f.user(first="Jordan", last="Kim")
    client.force_login(diner)
    assert client.get("/kitchen/items/new").status_code == 403
    assert client.post("/kitchen/items/new", item_data()).status_code == 403
    assert client.get("/kitchen/offerings/new").status_code == 403
    assert not MenuItem.objects.exists()


@pytest.mark.django_db
def test_az_02_cook_editing_another_cooks_item_gets_404(client, cook, other_cook):
    theirs = f.menu_item(other_cook, "Shakshuka", description="Their recipe.")
    client.force_login(cook.user)
    assert client.get(f"/kitchen/items/{theirs.pk}/edit").status_code == 404
    response = client.post(f"/kitchen/items/{theirs.pk}/edit", item_data(name="Stolen", description="Mine now"))
    assert response.status_code == 404
    assert client.post(f"/kitchen/items/{theirs.pk}/archive").status_code == 404
    theirs.refresh_from_db()
    assert (theirs.name, theirs.description, theirs.is_active) == ("Shakshuka", "Their recipe.", True)

    their_offering = f.offering(other_cook, title="Their Breakfast")
    assert client.get(f"/kitchen/offerings/{their_offering.pk}/edit").status_code == 404
    assert client.post(f"/kitchen/offerings/{their_offering.pk}/delete").status_code == 404
    assert Offering.objects.filter(pk=their_offering.pk, title="Their Breakfast").exists()


@pytest.mark.django_db
def test_az_07_offering_with_another_cooks_item_is_rejected(client, cook, other_cook):
    mine = f.menu_item(cook, "Buttermilk Pancakes")
    theirs = f.menu_item(other_cook, "French Toast")
    client.force_login(cook.user)
    response = client.post("/kitchen/offerings/new", offering_data([mine, theirs]))
    assert response.status_code == 200
    assert "items" in response.context["form"].errors
    assert not Offering.objects.exists()

    form = OfferingForm(cook, data=offering_data([theirs]))
    assert not form.is_valid() and "items" in form.errors


# --- MENU: menu items -------------------------------------------------------------------


@pytest.mark.django_db
def test_menu_01_unknown_allergen_is_rejected_by_form_and_db(cook):
    form = MenuItemForm(cook, data=item_data(allergens=["latex"]))
    assert not form.is_valid()
    assert "allergens" in form.errors

    with pytest.raises(IntegrityError), transaction.atomic():
        f.menu_item(cook, "Latex Surprise", allergens=["latex"])


@pytest.mark.django_db
def test_menu_02_item_without_allergen_confirmation_is_rejected(client, cook):
    client.force_login(cook.user)
    response = client.post("/kitchen/items/new", item_data(allergens_complete=None))
    assert response.status_code == 200
    assert "allergens_complete" in response.context["form"].errors
    assert not MenuItem.objects.exists()

    response = client.post("/kitchen/items/new", item_data())
    assert response.status_code == 302
    item = MenuItem.objects.get()
    assert item.cook == cook
    assert item.allergens == ["milk"]
    assert item.ingredients == "potatoes, butter, chives"
    assert item.allergens_confirmed_at is not None


@pytest.mark.django_db
def test_menu_03_dinner_side_shows_under_dinner_then_sides_on_cook_page(client, cook):
    client.force_login(cook.user)
    assert client.post("/kitchen/items/new", item_data(name="Baked Potato")).status_code == 302
    f.menu_item(cook, "French Toast")  # a breakfast main, so the grid has more than one section
    client.logout()

    html = client.get(f"/cooks/{cook.pk}").content.decode()
    grid = html[html.index('id="menu-heading"') :]
    dinner = grid.index(">Dinner<")
    sides = grid.index(">Sides<", dinner)
    assert grid.index("Baked Potato") > sides
    assert grid.index("French Toast") < dinner


@pytest.mark.django_db
def test_menu_04_second_active_specialty_for_a_meal_is_rejected(client, cook):
    f.menu_item(cook, "Buttermilk Pancakes", is_specialty=True)
    form = MenuItemForm(cook, data=item_data(name="French Toast", meal_type="breakfast", is_specialty="on"))
    assert not form.is_valid()
    assert "is_specialty" in form.errors

    client.force_login(cook.user)
    data = item_data(name="French Toast", meal_type="breakfast", course="main", is_specialty="on")
    assert client.post("/kitchen/items/new", data).status_code == 200
    assert MenuItem.objects.filter(is_specialty=True).count() == 1
    # A lunch specialty is fine: the rule is one per meal type.
    data = item_data(name="Tomato Soup", meal_type="lunch", course="main", is_specialty="on")
    assert client.post("/kitchen/items/new", data).status_code == 302
    with pytest.raises(IntegrityError), transaction.atomic():
        f.menu_item(cook, "Waffles", is_specialty=True)


# --- CONTRIB: grocery money -------------------------------------------------------------


@pytest.mark.django_db
def test_contrib_01_share_above_no_profit_cap_is_rejected_by_form_and_db(client, cook):
    item = f.menu_item(cook)
    client.force_login(cook.user)
    response = client.post("/kitchen/offerings/new", offering_data([item], share_per_seat="5.25"))
    assert response.status_code == 200
    assert NO_PROFIT in response.context["form"].errors["share_per_seat"][0]
    assert NO_PROFIT == "Diners together can't pay more than the groceries cost."
    assert not Offering.objects.exists()

    with pytest.raises(IntegrityError), transaction.atomic():
        f.offering(cook, grocery_estimate_cents=2000, capacity=4, share_per_seat_cents=525)

    response = client.post("/kitchen/offerings/new", offering_data([item], share_per_seat="5.00"))
    assert response.status_code == 302
    offering = Offering.objects.get()
    assert (offering.grocery_estimate_cents, offering.share_per_seat_cents, offering.capacity) == (2000, 500, 4)
    assert list(offering.items.all()) == [item]
    assert sorted(offering.needs.values_list("label", flat=True)) == ["1 dozen eggs", "1 lb spaghetti"]


@pytest.mark.django_db
def test_contrib_02_suggested_share_is_estimate_over_capacity_plus_one_rounded_to_quarter(client, cook):
    assert suggested_share_cents(2000, 4) == 400
    assert suggested_share_cents(1000, 3) == 250  # $2.50 exactly
    assert suggested_share_cents(1100, 3) == 275  # $2.75 rounded down to the quarter
    assert suggested_share_cents(1000, 2) == 325  # $3.33 rounds down to $3.25
    assert suggested_share_cents(0, 4) == 0

    offering = f.offering(cook, grocery_estimate_cents=2000, capacity=4, share_per_seat_cents=300)
    client.force_login(cook.user)
    html = client.get(f"/kitchen/offerings/{offering.pk}/edit").content.decode()
    assert "Suggested share: $4.00" in html

    # A blank share takes the suggestion.
    item = f.menu_item(cook)
    response = client.post("/kitchen/offerings/new", offering_data([item], share_per_seat=""))
    assert response.status_code == 302
    assert Offering.objects.latest("pk").share_per_seat_cents == 400


def test_contrib_10_money_is_integer_cents_and_renders_as_dollars():
    money_fields = []
    for model in apps.get_models():
        for field in model._meta.get_fields():
            assert not isinstance(field, models.FloatField | models.DecimalField), f"{model.__name__}.{field.name}"
            if re.search(r"cents|price|amount|cost", field.name):
                money_fields.append(field)
    assert {f.name for f in money_fields} == {"grocery_estimate_cents", "share_per_seat_cents", "share_cents"}
    for field in money_fields:
        assert field.name.endswith("_cents")
        assert isinstance(field, models.IntegerField)

    assert format_cents(0) == "$0.00"
    assert format_cents(5) == "$0.05"
    assert format_cents(400) == "$4.00"
    assert format_cents(2025) == "$20.25"
    rendered = Template("{% load money %}{{ a|money }} {{ b|money }}").render(Context({"a": 525, "b": 20000}))
    assert rendered == "$5.25 $200.00"


# --- Supporting kitchen flows (no plan ID; they keep the views covered) ------------------


@pytest.mark.django_db
def test_kitchen_setup_turns_a_diner_into_a_cook(client):
    diner = f.user(first="Jordan", last="Kim")
    client.force_login(diner)
    assert client.get("/kitchen").url == "/kitchen/setup"
    response = client.post("/kitchen/setup", {"bio": "I like to bake."})
    assert response.status_code == 200 and "food_safety" in response.context["form"].errors
    assert not CookProfile.objects.exists()

    response = client.post("/kitchen/setup", {"bio": "I like to bake.", "food_safety": "on"})
    assert response.status_code == 302 and response.url == "/kitchen"
    profile = CookProfile.objects.get(user=diner)
    assert profile.bio == "I like to bake." and profile.food_safety_ack_at is not None
    assert client.get("/kitchen/setup").url == "/kitchen"
    assert client.get("/kitchen").status_code == 200

    response = client.post("/kitchen/bio", {"bio": "I bake bread."})
    assert response.status_code == 302
    profile.refresh_from_db()
    assert profile.bio == "I bake bread."
    assert client.get("/kitchen/bio").status_code == 200


@pytest.mark.django_db
def test_kitchen_requires_login(client):
    for path in ("/kitchen", "/kitchen/setup", "/kitchen/items/new", "/kitchen/offerings/new"):
        response = client.get(path)
        assert response.status_code == 302 and response.url.startswith("/login?next="), path


@pytest.mark.django_db
def test_kitchen_page_lists_menu_and_meals(client, cook):
    f.menu_item(cook, "Buttermilk Pancakes", is_specialty=True)
    archived = f.menu_item(cook, "Old Waffles", is_active=False)
    f.offering(cook, title="Pancake Breakfast")
    f.offering(cook, title="Last Week Brunch", days_ahead=-7)
    client.force_login(cook.user)
    html = client.get("/kitchen").content.decode()
    for text in ("Buttermilk Pancakes", "Specialty", "Pancake Breakfast", "Last Week Brunch", "$4.00"):
        assert text in html, text
    assert archived.name not in html


@pytest.mark.django_db
def test_item_edit_and_archive(client, cook):
    item = f.menu_item(cook, "Pancakes", allergens=["wheat"])
    client.force_login(cook.user)
    assert client.get(f"/kitchen/items/{item.pk}/edit").status_code == 200
    data = item_data(name="Buttermilk Pancakes", meal_type="breakfast", course="main", allergens=["wheat", "egg"])
    assert client.post(f"/kitchen/items/{item.pk}/edit", data).status_code == 302
    item.refresh_from_db()
    assert item.name == "Buttermilk Pancakes" and item.allergens == ["wheat", "egg"]

    # A second active dish with the same name for the same meal is rejected.
    f.menu_item(cook, "French Toast")
    form = MenuItemForm(cook, data=item_data(name="french toast", meal_type="breakfast"))
    assert not form.is_valid() and "name" in form.errors

    assert client.get(f"/kitchen/items/{item.pk}/archive").status_code == 405
    assert client.post(f"/kitchen/items/{item.pk}/archive").status_code == 302
    item.refresh_from_db()
    assert not item.is_active


@pytest.mark.django_db
def test_allergen_lock_while_item_has_active_bookings(client, cook):
    item = f.menu_item(cook, "Buttermilk Pancakes", allergens=["wheat"])
    offering = f.offering(cook)
    offering.items.add(item)
    f.booking(offering, f.user(first="Jordan", last="Kim"), status="confirmed")
    form = MenuItemForm(cook, instance=item, data=item_data(name=item.name, meal_type="breakfast", allergens=["egg"]))
    assert not form.is_valid() and "allergens" in form.errors
    form = MenuItemForm(cook, instance=item, data=item_data(name=item.name, meal_type="breakfast", allergens=["wheat"]))
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_offering_edit_keeps_claimed_needs_and_validates_times(client, cook):
    item = f.menu_item(cook)
    offering = f.offering(cook, title="Pancake Breakfast")
    offering.items.add(item)
    diner = f.user(first="Jordan", last="Kim")
    claimed = OfferingNeed.objects.create(
        offering=offering,
        label="1 dozen eggs",
        claimed_by_booking=f.booking(offering, diner, contribution="ingredients"),
    )
    OfferingNeed.objects.create(offering=offering, label="1 lb spaghetti")
    client.force_login(cook.user)
    html = client.get(f"/kitchen/offerings/{offering.pk}/edit").content.decode()
    assert "1 lb spaghetti" in html and "1 dozen eggs" in html

    data = offering_data([item], title="Pancake Brunch", bring_list="1 bag of rice", share_per_seat="0")
    assert client.post(f"/kitchen/offerings/{offering.pk}/edit", data).status_code == 302
    offering.refresh_from_db()
    assert offering.title == "Pancake Brunch" and offering.share_per_seat_cents == 0
    assert sorted(offering.needs.values_list("label", flat=True)) == ["1 bag of rice", "1 dozen eggs"]
    assert OfferingNeed.objects.filter(pk=claimed.pk).exists()

    late = offering_data([item])
    late["booking_cutoff_at"], late["serve_at"] = late["serve_at"], late["booking_cutoff_at"]
    response = client.post("/kitchen/offerings/new", late)
    assert "booking_cutoff_at" in response.context["form"].errors

    past = (timezone.localtime() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    response = client.post("/kitchen/offerings/new", offering_data([item], serve_at=past, booking_cutoff_at=past))
    assert "serve_at" in response.context["form"].errors

    lunch = f.menu_item(cook, "Tomato Soup", meal_type="lunch")
    response = client.post("/kitchen/offerings/new", offering_data([lunch]))
    assert "items" in response.context["form"].errors

    response = client.post("/kitchen/offerings/new", offering_data([item], bring_list="x" * 81))
    assert "bring_list" in response.context["form"].errors
    assert Offering.objects.count() == 1


@pytest.mark.django_db
def test_offering_delete_only_without_bookings(client, cook):
    empty = f.offering(cook, title="Nobody Came")
    booked = f.offering(cook, title="Popular Brunch")
    f.booking(booked, f.user(first="Jordan", last="Kim"))
    client.force_login(cook.user)
    assert client.post(f"/kitchen/offerings/{empty.pk}/delete").status_code == 302
    assert not Offering.objects.filter(pk=empty.pk).exists()
    response = client.post(f"/kitchen/offerings/{booked.pk}/delete", follow=True)
    assert Offering.objects.filter(pk=booked.pk).exists()
    assert "has bookings" in response.content.decode()


@pytest.mark.django_db
def test_claimed_bring_list_label_is_escaped_on_edit_form(client, cook):
    offering = f.offering(cook)
    booking = f.booking(offering, f.user(first="Jordan", last="Kim"), contribution="ingredients")
    OfferingNeed.objects.create(offering=offering, label="<b>eggs</b>", claimed_by_booking=booking)
    client.force_login(cook.user)
    html = client.get(f"/kitchen/offerings/{offering.pk}/edit").content.decode()
    assert "&lt;b&gt;eggs&lt;/b&gt;" in html
    assert "<b>eggs</b>" not in html
