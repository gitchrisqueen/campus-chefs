"""The end-to-end journeys E2E-01..05 (plan 7.2) against the running stack.

`make e2e` reseeds the demo data first. The seed (core/management/commands/seed_demo.py) gives:
- "Pancake Breakfast": the demo cook's meal tomorrow, $4.00 share per seat, 2 of 6 seats taken;
- "Steak Night": the demo cook's meal yesterday, with the demo diner's confirmed $4.00 booking.
E2E-01, E2E-03 and E2E-05 each take one more pancake seat (5 of 6 in all). New accounts get a
unique synthetic `.example` email on every run.
"""

import re

import pytest
from playwright.sync_api import expect

from tests.e2e.helpers import demo_login, unique_email

pytestmark = pytest.mark.e2e

# A throwaway password for throwaway synthetic accounts in the local demo; not a credential.
PASSWORD = "e2e-Synthetic-pass-2026"  # gitleaks:allow
PUBLIC_PAGES = ["/", "/how-it-works", "/safety", "/privacy", "/register", "/login", "/search", "/search?q=pancakes"]


def _search_pancakes(page, base_url: str) -> tuple[str, str]:
    """Return (offering path, cook path) of the seeded Pancake Breakfast."""
    page.goto(f"{base_url}/search?q=pancakes")
    card = page.locator(".offer-card", has_text="Pancake Breakfast")
    return (
        card.locator(".offer-title a").get_attribute("href"),
        card.locator(".offer-cook a").get_attribute("href"),
    )


def test_e2e_01_diner_books_with_grocery_share_and_cook_confirms(new_page, base_url):
    diner = new_page()
    demo_login(diner, base_url, "diner")
    diner.goto(f"{base_url}/search")
    diner.fill("#q", "pancakes")
    card = diner.locator("#results .offer-card", has_text="Pancake Breakfast")
    card.get_by_role("link", name="Pancake Breakfast").click()
    expect(diner.get_by_role("heading", level=1)).to_have_text("Pancake Breakfast")

    form = diner.locator(".booking-form")
    form.get_by_label("Seats").select_option("1")
    share = form.get_by_role("radio", name=re.compile(r"^Grocery share: "))
    share.check()
    per_seat = re.search(r"\$(\d+\.\d\d) per seat", share.evaluate("el => el.labels[0].textContent")).group(1)
    form.get_by_role("checkbox", name=re.compile(r"^I have read the allergens")).check()
    form.get_by_role("button", name="Request seats").click()

    panel = diner.locator("#booking-panel")
    expect(panel).to_contain_text("Request sent.")
    booking_url = panel.get_by_role("link", name="View your booking").get_attribute("href")

    cook = new_page()
    demo_login(cook, base_url, "cook")
    cook.goto(f"{base_url}{booking_url}")
    expect(cook.locator(".page-head")).to_contain_text("Requested")
    cook.get_by_role("button", name="Confirm").click()
    expect(cook.locator(".messages")).to_contain_text("Booking confirmed.")

    diner.goto(f"{base_url}{booking_url}")
    expect(diner.locator(".page-head .eyebrow")).to_have_text("Booking · Confirmed")
    expect(diner.locator(".timeline")).to_contain_text("Confirmed")
    expect(diner.locator(".contribution")).to_have_text(f"Grocery share: ${per_seat}, pay the cook at pickup")


def test_e2e_02_cook_marks_share_received_and_completed_then_diner_reviews(new_page, base_url):
    diner = new_page()
    demo_login(diner, base_url, "diner")
    booking_url = diner.get_by_role("link", name="Steak Night").get_attribute("href")

    cook = new_page()
    demo_login(cook, base_url, "cook")
    cook.goto(f"{base_url}{booking_url}")
    expect(cook.locator(".contribution")).to_have_text("Grocery share: $4.00, pay the cook at pickup")
    cook.get_by_role("button", name="Mark contribution received").click()
    expect(cook.locator(".messages")).to_contain_text("Contribution marked received.")
    expect(cook.get_by_text("Received by the cook")).to_be_visible()
    cook.get_by_role("button", name="Mark completed").click()
    expect(cook.locator(".messages")).to_contain_text("Booking marked completed.")
    expect(cook.locator(".page-head .eyebrow")).to_have_text("Booking · Completed")

    the_good = f"Steak cooked just right (e2e {unique_email('r').split('@')[0]})."
    diner.goto(f"{base_url}{booking_url}")
    review = diner.locator('form[action$="/review"]')
    review.get_by_label("5 stars").check()
    review.get_by_label("The good").fill(the_good)
    review.get_by_role("button", name="Post review").click()
    expect(diner.locator(".messages")).to_contain_text("Thanks, your review is posted.")

    diner.locator(".page-head").get_by_role("link").click()  # the cook's public page
    entry = diner.locator(".review-list li", has_text=the_good)
    expect(entry).to_have_count(1)
    expect(entry).to_contain_text(f"The good: {the_good}")
    expect(entry).to_contain_text("5 out of 5")


# --- E2E-03: keyboard only ---------------------------------------------------------------

FOCUS_INFO = """() => {
  const el = document.activeElement;
  const ring = n => {
    const s = getComputedStyle(n);
    return s.outlineStyle !== "none" && parseFloat(s.outlineWidth) >= 2 && s.outlineColor !== "rgba(0, 0, 0, 0)";
  };
  const box = el.getBoundingClientRect();
  const tile = el.closest(".choice");
  const text = (el.getAttribute("name") || el.textContent || "").trim().slice(0, 40);
  return {
    name: `${el.tagName.toLowerCase()}#${el.id} ${text}`,
    body: el === document.body,
    visible: box.width > 0 && box.height > 0,
    ring: ring(el) || (tile !== null && ring(tile)),
  };
}"""


class Keyboard:
    """Moves focus with Tab only, and records every focus stop that has no visible outline."""

    def __init__(self, page):
        self.page = page
        self.unringed: list[str] = []

    def tab_to(self, selector: str, limit: int = 80) -> None:
        for _ in range(limit):
            self.page.keyboard.press("Tab")
            info = self.page.evaluate(FOCUS_INFO)
            if info["body"]:
                continue
            if not (info["visible"] and info["ring"]):
                self.unringed.append(f"{self.page.url} {info['name']}")
            if self.page.evaluate("s => document.activeElement.matches(s)", selector):
                return
        raise AssertionError(f"Tab never reached {selector} on {self.page.url}")


def test_e2e_03_keyboard_only_register_and_book_with_visible_focus(new_page, base_url):
    page = new_page()
    keys = Keyboard(page)
    email = unique_email("keyboard")

    page.goto(f"{base_url}/register")
    for selector, text in (
        ("#id_email", email),
        ("#id_password1", PASSWORD),
        ("#id_password2", PASSWORD),
        ("#id_first_name", "Kai"),
        ("#id_last_name", "Keys"),
    ):
        keys.tab_to(selector)
        page.keyboard.type(text)
    keys.tab_to("#id_campus")
    page.keyboard.type("Larkspur")  # select type-ahead
    expect(page.locator("#id_campus option:checked")).to_have_text(re.compile("^Larkspur"))
    keys.tab_to('input[name="role"]')
    if not page.evaluate("document.activeElement.value") == "eat":
        page.keyboard.press("ArrowUp")
    page.keyboard.press("Space")
    expect(page.locator('input[name="role"][value="eat"]')).to_be_checked()
    keys.tab_to("#id_adult")
    page.keyboard.press("Space")
    expect(page.locator("#id_adult")).to_be_checked()
    keys.tab_to('main form[action="/register"] button[type="submit"]')
    page.keyboard.press("Enter")
    page.wait_for_url(f"{base_url}/me")
    expect(page.get_by_role("heading", level=1)).to_have_text("Kai K.")

    page.goto(f"{base_url}/search")
    keys.tab_to("#q")
    page.keyboard.type("pancakes")
    page.keyboard.press("Enter")
    link = page.locator("#results .offer-card .offer-title a", has_text="Pancake Breakfast")
    expect(link).to_be_visible()
    keys.tab_to(f'#results a[href="{link.get_attribute("href")}"]')
    page.keyboard.press("Enter")
    expect(page.get_by_role("heading", level=1)).to_have_text("Pancake Breakfast")

    keys.tab_to("#id_allergen_ack")
    page.keyboard.press("Space")
    expect(page.locator("#id_allergen_ack")).to_be_checked()
    keys.tab_to('.booking-form button[type="submit"]')
    page.keyboard.press("Enter")
    expect(page.locator("#booking-panel")).to_contain_text("Request sent.")
    keys.tab_to("#booking-panel a.btn")
    page.keyboard.press("Enter")
    expect(page.locator(".page-head .eyebrow")).to_have_text("Booking · Requested")

    assert keys.unringed == []


# --- E2E-04 and E2E-05 -------------------------------------------------------------------


def test_e2e_04_no_horizontal_scroll_at_320px(new_page, base_url):
    page = new_page(viewport={"width": 320, "height": 800})
    offering_url, cook_url = _search_pancakes(page, base_url)
    wide = {}
    for path in [*PUBLIC_PAGES, cook_url, offering_url, "/no-such-page"]:
        page.goto(f"{base_url}{path}")
        width = page.evaluate("document.documentElement.scrollWidth")
        if width > 320:
            wide[path] = width
    assert wide == {}


@pytest.fixture
def no_js_page(browser):
    """A context with JavaScript off: htmx never loads, so every form is a full-page request."""
    context = browser.new_context(java_script_enabled=False)
    yield context.new_page()
    context.close()


def test_e2e_05_search_and_booking_work_without_javascript(no_js_page, base_url):
    page = no_js_page
    page.goto(f"{base_url}/search")
    page.fill("#q", "pancakes")
    page.locator('main form[action="/search"]').get_by_role("button", name="Search").click()
    page.wait_for_url(re.compile(r"/search\?.*q=pancakes"))
    expect(page.locator("#results .offer-card", has_text="Pancake Breakfast")).to_have_count(1)
    offering_url = page.locator("#results .offer-title a", has_text="Pancake Breakfast").get_attribute("href")

    # Register (a full-page POST), then request a seat by bringing an item from the bring list.
    page.goto(f"{base_url}/register")
    form = page.locator('main form[action="/register"]')
    form.locator("#id_email").fill(unique_email("nojs"))
    form.locator("#id_password1").fill(PASSWORD)
    form.locator("#id_password2").fill(PASSWORD)
    form.locator("#id_first_name").fill("Noa")
    form.locator("#id_last_name").fill("Script")
    form.locator("#id_campus").select_option(label="Larkspur State University (Demo)")
    form.locator('input[name="role"][value="eat"]').check()
    form.locator("#id_adult").check()
    form.get_by_role("button", name="Create account").click()
    page.wait_for_url(f"{base_url}/me")

    page.goto(f"{base_url}{offering_url}")
    booking = page.locator(".booking-form")
    booking.get_by_role("radio", name="Bring an item from the bring list instead").check()
    need = booking.locator("#id_need option").nth(1)
    need_label = need.text_content().strip()
    booking.locator("#id_need").select_option(need.get_attribute("value"))
    booking.get_by_role("checkbox", name=re.compile(r"^I have read the allergens")).check()
    booking.get_by_role("button", name="Request seats").click()

    page.wait_for_url(re.compile(r"/bookings/\d+$"))
    expect(page.locator(".page-head .eyebrow")).to_have_text("Booking · Requested")
    expect(page.locator(".contribution")).to_have_text(f"Bring: {need_label}")
