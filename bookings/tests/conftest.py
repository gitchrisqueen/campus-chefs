import pytest

from tests import factories as f


@pytest.fixture
def cook(db):
    return f.cook(first="Marcus", last="Bell", email="marcus.b@larkspur.example")


@pytest.fixture
def diner(db):
    return f.user(first="Ava", last="Reyes", email="ava.r@larkspur.example")


@pytest.fixture
def offering(cook):
    """$20.00 groceries, 4 seats, $4.00 share per seat, one dish with egg and wheat."""
    meal = f.offering(cook, title="Pancake Breakfast", pickup_note="Lobby of North Hall (Demo).")
    meal.items.add(f.menu_item(cook, "Buttermilk Pancakes", allergens=["egg", "wheat"]))
    return meal
