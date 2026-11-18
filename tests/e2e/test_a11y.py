"""Accessibility in a real browser (plan 4.4, 7.1, 7.2).

A11Y-01 runs the vendored axe-core (tests/e2e/vendor/axe.min.js, version and integrity in
docs/architecture.md) with the tags wcag2a, wcag2aa, wcag21aa and wcag22aa. No rule is
disabled: any violation fails, in light and in dark mode.
"""

import re

import pytest
from playwright.sync_api import expect

from tests.e2e.helpers import axe_violations, demo_login

pytestmark = pytest.mark.e2e

ANONYMOUS_PAGES = ["/", "/how-it-works", "/safety", "/privacy", "/register", "/login", "/search?q=pancakes"]
DINER_PAGES = ["/me", "/me/edit"]
COOK_PAGES = ["/me", "/kitchen", "/kitchen/items/new", "/kitchen/offerings/new"]


def _check(page, label: str, found: dict[str, list[str]]) -> None:
    violations = axe_violations(page)
    if violations:
        found[label] = violations


def _href(page, selector: str) -> str:
    return page.locator(selector).first.get_attribute("href")


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a11y_01_axe_finds_no_violations(browser, base_url, scheme):
    found: dict[str, list[str]] = {}

    def new_page():
        context = browser.new_context(color_scheme=scheme, viewport={"width": 1280, "height": 900})
        return context, context.new_page()

    # Anonymous visitor: the public pages, a search with results, a cook page and an offering.
    context, page = new_page()
    for path in ANONYMOUS_PAGES:
        page.goto(f"{base_url}{path}")
        _check(page, path, found)
    page.goto(f"{base_url}/")
    page.fill("#q", "pancakes")
    expect(page.locator("#results .offer-card").first).to_be_visible()
    _check(page, "/ (live search results)", found)
    page.goto(f"{base_url}/register")
    page.locator('main form[action="/register"] button[type="submit"]').click()
    expect(page.locator(".error-summary")).to_be_visible()
    _check(page, "/register (errors)", found)
    page.goto(f"{base_url}/search?q=pancakes")
    offering_url = _href(page, ".offer-card .offer-title a")
    cook_url = _href(page, ".offer-card .offer-cook a")
    for path in (cook_url, offering_url, "/no-such-page"):
        page.goto(f"{base_url}{path}")
        _check(page, path, found)
    context.close()

    # The demo diner: account pages, the booking form, a booking with its actions.
    context, page = new_page()
    demo_login(page, base_url, "diner")
    for path in DINER_PAGES:
        page.goto(f"{base_url}{path}")
        _check(page, f"{path} (diner)", found)
    page.goto(f"{base_url}{offering_url}")
    expect(page.locator(".booking-form")).to_be_visible()
    _check(page, f"{offering_url} (diner, booking form)", found)
    page.locator('.booking-form button[type="submit"]').click()  # no allergen box: the error state
    expect(page.locator(".booking-form .error-summary")).to_be_visible()
    _check(page, f"{offering_url} (diner, booking form errors)", found)
    page.goto(f"{base_url}/me")
    booking_url = page.get_by_role("link", name="Steak Night").get_attribute("href")
    page.goto(f"{base_url}{booking_url}")
    _check(page, f"{booking_url} (diner)", found)
    context.close()

    # The demo cook: account, kitchen and menu forms, and the same booking from the cook's side.
    context, page = new_page()
    demo_login(page, base_url, "cook")
    for path in COOK_PAGES:
        page.goto(f"{base_url}{path}")
        _check(page, f"{path} (cook)", found)
    page.goto(f"{base_url}{booking_url}")
    _check(page, f"{booking_url} (cook)", found)
    context.close()

    assert found == {}


def test_a11y_03_home_steps_are_an_ordered_list_of_three_without_digit_images(page, base_url):
    page.goto(f"{base_url}/")
    steps = page.locator("ol.steps")
    expect(steps).to_have_count(1)
    items = steps.locator(":scope > li")
    expect(items).to_have_count(3)
    expect(steps.get_by_role("listitem")).to_have_count(3)

    expect(items.locator("h3")).to_have_text(["Register.", "Search.", "Eat!"])
    expect(steps.locator("img, svg, picture")).to_have_count(0)
    for i in range(3):
        expect(items.nth(i).get_by_role("link")).to_have_count(1)

    # The numbered tile is CSS-generated (a counter), with empty alternative text, so a screen
    # reader hears the list position once and never a stray digit.
    content = items.first.evaluate("li => getComputedStyle(li, '::before').content")
    assert "counter" in content or content.strip('"') == "1", content
    snapshot = steps.aria_snapshot()
    assert not re.search(r"^\s*- text: \d\s*$", snapshot, re.M), snapshot
    assert "Register." in snapshot and "Eat!" in snapshot

    # Three columns from 40rem, one stacked column below it (plan 4.3).
    def tops() -> list[float]:
        return [items.nth(i).bounding_box()["y"] for i in range(3)]

    page.set_viewport_size({"width": 1280, "height": 900})
    wide = tops()
    assert max(wide) - min(wide) < 1, wide
    page.set_viewport_size({"width": 390, "height": 844})
    narrow = tops()
    assert narrow[0] < narrow[1] < narrow[2], narrow
