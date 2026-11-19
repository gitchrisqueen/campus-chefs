"""Art-director rules on the later-phase screens: no eyebrow labels, no middle-dot strings, and
tracked uppercase text only on the `.eyebrow` rule (home hero, /safety, /privacy)."""

import re
from pathlib import Path

import pytest
import tinycss2

from bookings.models import Booking
from tests import factories as f

S = Booking.Status
APP_CSS = Path(__file__).resolve().parents[2] / "static" / "css" / "app.css"


def _visible(client, url: str) -> str:
    """The page body with the <title> (where ' · ' is allowed), scripts and tags removed."""
    html = client.get(url).content.decode("utf-8")
    html = re.sub(r"<title>.*?</title>|<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


@pytest.mark.django_db
def test_design_rules_no_middle_dot_and_no_eyebrow_on_later_screens(client, settings, offering, diner):
    settings.CC_DEMO_MODE = True  # demo-only markup (banner, footer) renders in demo mode
    booking = f.booking(offering, diner, status=S.CONFIRMED, seats=2, contribution="share", share_cents=800)
    pages = [
        (diner, f"/bookings/{booking.pk}"),
        (diner, "/me"),
        (offering.cook.user, f"/bookings/{booking.pk}"),
        (offering.cook.user, "/me"),
        (offering.cook.user, "/kitchen"),
        (diner, f"/offerings/{offering.pk}"),
        (offering.cook.user, f"/offerings/{offering.pk}"),
        (None, f"/search?q={offering.cook.user.first_name}"),
        (None, f"/cooks/{offering.cook_id}"),
        (diner, f"/cooks/{offering.cook_id}"),
    ]
    for user, url in pages:
        if user is None:
            client.logout()
        else:
            client.force_login(user)
        raw = client.get(url).content.decode("utf-8")
        assert 'class="eyebrow"' not in raw, url
        assert "·" not in _visible(client, url), url
    client.force_login(diner)
    detail = client.get(f"/bookings/{booking.pk}").content.decode("utf-8")
    assert re.search(r'class="badge"[^>]*data-booking-status[^>]*>\s*Confirmed\s*<', detail)


@pytest.mark.django_db
def test_design_rules_search_results_render_cards_without_eyebrows(client, offering):
    raw = client.get(f"/search?q={offering.cook.user.first_name}").content.decode("utf-8")
    assert 'class="offer-card"' in raw, "the search check needs at least one result card"
    kind = re.search(r'<span class="offer-kind">([^<]+)</span>', raw)
    assert kind and kind.group(1) == offering.get_meal_type_display()


def _rules_with(declaration: str) -> list[str]:
    """Selectors of every style rule (at any @layer or @media depth) that sets `declaration`."""
    name, value = (part.strip() for part in declaration.split(":"))
    found: list[str] = []

    def walk(rules) -> None:
        for rule in rules:
            if rule.type == "at-rule" and rule.content is not None:
                walk(tinycss2.parse_blocks_contents(rule.content, skip_comments=True, skip_whitespace=True))
            elif rule.type == "qualified-rule":
                decls = tinycss2.parse_blocks_contents(rule.content, skip_comments=True, skip_whitespace=True)
                for decl in decls:
                    if decl.type == "declaration" and decl.lower_name == name:
                        if tinycss2.serialize(decl.value).strip().lower() == value:
                            found.append(tinycss2.serialize(rule.prelude).strip())

    walk(tinycss2.parse_stylesheet(APP_CSS.read_text(encoding="utf-8"), skip_comments=True, skip_whitespace=True))
    return found


def test_design_rules_uppercase_only_on_the_eyebrow_rule():
    assert _rules_with("text-transform: uppercase") == [".eyebrow"]
