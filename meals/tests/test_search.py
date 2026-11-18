"""Phase 5: search (plan 3.2), its privacy rule (AZ-06) and the chip-in badges (CONTRIB-08)."""

import re
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from accounts.models import User
from core import seed_data
from meals.models import CookProfile, Offering
from meals.search import search_offerings
from tests import factories as f


def titles(response) -> list[str]:
    return [o.title for o in response.context["page"].object_list]


@pytest.fixture
def cook(db):
    return f.cook(first="Mateo", last="Lindqvist", email="mateo.l@larkspur.example")


def dish_offering(cook, title, *, days_ahead=2, items=(), **extra):
    offering = f.offering(cook, title=title, days_ahead=days_ahead, **extra)
    for name, kwargs in items:
        offering.items.add(f.menu_item(cook, name, **kwargs))
    return offering


@pytest.mark.django_db
def test_srch_01_ingredient_match(client, cook):
    dish_offering(cook, "Lentil Soup Lunch", items=[("Red Soup", {"ingredients": "red lentils, onion, cumin"})])
    dish_offering(cook, "Pancake Breakfast", items=[("Pancakes", {"ingredients": "flour, eggs"})])
    assert titles(client.get("/search", {"q": "lentils"})) == ["Lentil Soup Lunch"]


@pytest.mark.django_db
def test_srch_02_cook_first_name_match(client, cook):
    dish_offering(cook, "Pancake Breakfast", items=[("Pancakes", {})])
    dish_offering(cook, "Waffle Breakfast", days_ahead=3, items=[("Waffles", {})])
    other = f.cook(first="Elena", last="Ortiz")
    dish_offering(other, "Elena's Lunch", items=[("Soup", {})])
    response = client.get("/search", {"q": "Mateo"})
    assert titles(response) == ["Pancake Breakfast", "Waffle Breakfast"]
    assert "Mateo L." in response.content.decode()


@pytest.mark.django_db
def test_srch_04_exclude_allergen_and_disclaimer(client, cook):
    dish_offering(cook, "Satay Night", items=[("Peanut Satay", {"allergens": ["peanuts"]}), ("Rice", {})])
    dish_offering(cook, "Pasta Night", items=[("Pasta", {"allergens": ["wheat"]})])
    response = client.get("/search", {"exclude": "peanuts"})
    assert titles(response) == ["Pasta Night"]
    for offering in response.context["page"].object_list:
        assert all("peanuts" not in item.allergens for item in offering.items.all())
    assert "not a safety guarantee" in response.content.decode()


@pytest.mark.django_db
def test_srch_05_diet_tag_must_be_on_every_item(client, cook):
    vegan = {"dietary_tags": ["vegan"]}
    dish_offering(cook, "All Vegan", items=[("Tofu", vegan), ("Fruit", vegan)])
    dish_offering(cook, "Half Vegan", items=[("Salad", vegan), ("Cheese", {"dietary_tags": []})])
    assert titles(client.get("/search", {"diet": "vegan"})) == ["All Vegan"]


@pytest.mark.django_db
def test_srch_06_campus_filter_open_future_cutoff_ordered(client, cook):
    cobalt = f.campus("cobalt-bay", "Cobalt Bay Institute (Demo)")
    far = f.cook(first="Elena", last="Ortiz", campus=cobalt)
    later = f.offering(cook, title="Later", days_ahead=4)
    sooner = f.offering(cook, title="Sooner", days_ahead=1)
    f.offering(cook, title="Cancelled", status="cancelled")
    past_cutoff = timezone.now() + timedelta(hours=1)
    f.offering(cook, title="Past Cutoff", serve_at=past_cutoff, booking_cutoff_at=timezone.now() - timedelta(minutes=5))
    f.offering(far, title="Other Campus")
    response = client.get("/search", {"campus": "larkspur"})
    assert titles(response) == [sooner.title, later.title]

    assert [o.title for o in search_offerings()] == ["Sooner", "Other Campus", "Later"]


@pytest.mark.django_db
def test_srch_07_htmx_gets_partial_plain_get_gets_full_page(client, cook):
    dish_offering(cook, "Pancake Breakfast", items=[("Buttermilk Pancakes", {})])
    partial = client.get("/search", {"q": "pancakes"}, headers={"HX-Request": "true"})
    html = partial.content.decode()
    assert "Buttermilk Pancakes" in html and "<html" not in html

    full = client.get("/search", {"q": "pancakes"})
    html = full.content.decode()
    assert "Buttermilk Pancakes" in html and "<html" in html
    assert 'id="q"' in html and 'id="results"' in html and 'aria-live="polite"' in html

    empty = client.get("/search", {"q": "zzz"}, headers={"HX-Request": "true"})
    assert "No meals match" in empty.content.decode()


@pytest.mark.django_db
def test_srch_08_echoed_query_is_escaped(client):
    response = client.get("/search", {"q": "<script>alert(1)</script>"})
    html = response.content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


@pytest.mark.django_db
@pytest.mark.parametrize("q", ["%", "_"])
def test_srch_09_like_wildcards_match_nothing(client, cook, q):
    dish_offering(cook, "Pancake Breakfast", items=[("Buttermilk Pancakes", {"description": "Fluffy."})])
    assert titles(client.get("/search", {"q": q})) == []


@pytest.mark.django_db
def test_srch_10_last_name_is_never_searched(client, cook):
    dish_offering(cook, "Pancake Breakfast", items=[("Buttermilk Pancakes", {})])
    assert titles(client.get("/search", {"q": "Lindq"})) == []
    assert titles(client.get("/search", {"q": "Mat"})) == ["Pancake Breakfast"]


@pytest.mark.django_db
def test_az_06_public_pages_show_no_email_and_no_full_last_name(client):
    call_command("seed_demo")
    emails = list(User.objects.values_list("email", flat=True))
    last_names = list(User.objects.values_list("last_name", flat=True))
    pages = ["/search", "/search?q=a", "/search?page=2"]
    pages += [f"/cooks/{pk}" for pk in CookProfile.objects.values_list("pk", flat=True)]
    pages += [f"/offerings/{pk}" for pk in Offering.objects.values_list("pk", flat=True)]
    for path in pages:
        response = client.get(path)
        assert response.status_code == 200, path
        html = response.content.decode()
        for email in emails:
            assert email not in html, (path, email)
        for last in last_names:
            assert not re.search(rf"\b{re.escape(last)}\b", html), (path, last)
    assert seed_data.PERSONA_COOK[2] == "Bell"  # the check covers the demo personas too


@pytest.mark.django_db
def test_contrib_08_chip_in_badges_as_seeded_and_max_share_filter(client):
    call_command("seed_demo")
    html = client.get("/search").content.decode()
    for badge in (">Free<", "$4.00 grocery share per seat", "or bring an item"):
        assert badge in html, badge

    demo_cook = CookProfile.objects.get(user__email=seed_data.PERSONA_COOK[0])
    html = client.get(f"/cooks/{demo_cook.pk}").content.decode()
    assert "$4.00 grocery share per seat" in html and "or bring an item" in html
    free = Offering.objects.filter(share_per_seat_cents=0, needs__isnull=True, serve_at__gt=timezone.now()).first()
    assert ">Free<" in client.get(f"/cooks/{free.cook_id}").content.decode()

    response = client.get("/search", {"max_share": "4"})
    listed = response.context["page"].object_list
    assert listed and all(o.share_per_seat_cents <= 400 for o in listed)
    above = Offering.objects.filter(share_per_seat_cents__gt=400, status="open", booking_cutoff_at__gt=timezone.now())
    assert above.exists()
    assert not {o.pk for o in listed} & set(above.values_list("pk", flat=True))
    assert "$6.00 grocery share per seat" not in response.content.decode()


# --- Supporting search tests (no plan ID) ------------------------------------------------


@pytest.mark.django_db
def test_search_meal_date_filters_invalid_input_and_pagination(client, cook):
    first = f.offering(cook, title="Lunch One", meal_type="lunch", days_ahead=1)
    f.offering(cook, title="Breakfast Two", days_ahead=2)
    day = timezone.localtime(first.serve_at).date().isoformat()
    assert titles(client.get("/search", {"meal": "lunch"})) == ["Lunch One"]
    assert titles(client.get("/search", {"date": day})) == ["Lunch One"]

    response = client.get("/search", {"campus": "nowhere", "max_share": "-1", "q": "Lunch"})
    assert response.status_code == 200
    assert "campus" in response.context["form"].errors and "max_share" in response.context["form"].errors
    assert titles(response) == []  # q still applies; the invalid filters are ignored

    for n in range(21):
        f.offering(cook, title=f"Bulk {n:02d}", days_ahead=10)
    page_one = client.get("/search")
    assert len(titles(page_one)) == 20 and "Next page" in page_one.content.decode()
    page_two = client.get("/search", {"page": 2})
    assert len(titles(page_two)) == 3 and "Previous page" in page_two.content.decode()


@pytest.mark.django_db
def test_home_search_box_targets_search(client):
    html = client.get("/").content.decode()
    assert 'action="/search"' in html and 'hx-get="/search"' in html
    assert client.get("/search/stub").status_code == 404
    assert 'href="/search"' in html, "the main nav links to search"
