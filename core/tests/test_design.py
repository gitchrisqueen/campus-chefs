"""Design system and static pages (plan 4, 5.5, phase 8a).

UX-01 reads the colour tokens straight from static/css/app.css, so a token change that breaks
contrast fails here before any browser test runs.
"""

import re
from pathlib import Path

import pytest
import tinycss2
from django.core.management import call_command
from django.test import RequestFactory
from django.views.defaults import server_error

from meals.models import CookProfile, MenuItem

ROOT = Path(__file__).resolve().parents[2]
APP_CSS = ROOT / "static" / "css" / "app.css"
PUBLIC_PAGES = ["/", "/how-it-works", "/safety", "/privacy"]


# --- UX-01: token contrast ---------------------------------------------------------------


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _luminance(value: str) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in _hex_to_rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    """WCAG 2.x contrast ratio between two hex colours."""
    hi, lo = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _root_tokens(rules) -> dict[str, str]:
    tokens: dict[str, str] = {}
    for rule in rules:
        if rule.type == "qualified-rule" and tinycss2.serialize(rule.prelude).strip() == ":root":
            for decl in tinycss2.parse_blocks_contents(rule.content, skip_comments=True, skip_whitespace=True):
                if decl.type == "declaration" and decl.name.startswith("--cc-"):
                    tokens[decl.name] = tinycss2.serialize(decl.value).strip().lower()
    return tokens


def css_themes() -> dict[str, dict[str, str]]:
    """Return {"light": tokens, "dark": tokens} from the `@layer tokens` block of app.css."""
    sheet = tinycss2.parse_stylesheet(APP_CSS.read_text(encoding="utf-8"), skip_comments=True, skip_whitespace=True)
    layer = next(
        r
        for r in sheet
        if r.type == "at-rule" and r.lower_at_keyword == "layer" and r.content is not None
        if tinycss2.serialize(r.prelude).strip() == "tokens"
    )
    rules = tinycss2.parse_blocks_contents(layer.content, skip_comments=True, skip_whitespace=True)
    light = _root_tokens(rules)
    dark_media = next(
        r
        for r in rules
        if r.type == "at-rule" and r.lower_at_keyword == "media" and "dark" in tinycss2.serialize(r.prelude)
    )
    dark = {**light, **_root_tokens(tinycss2.parse_blocks_contents(dark_media.content, skip_whitespace=True))}
    return {"light": light, "dark": dark}


# (foreground token, background token, minimum ratio). Plan 7.2 UX-01 pairs first, then the
# component pairs this phase adds (badges, notices, the footer's sunken surface).
CONTRAST_PAIRS = [
    ("--cc-text", "--cc-bg", 4.5),
    ("--cc-text", "--cc-surface", 4.5),
    ("--cc-on-brand", "--cc-brand", 4.5),
    ("--cc-accent", "--cc-bg", 4.5),
    ("--cc-muted", "--cc-bg", 4.5),
    ("--cc-muted", "--cc-surface", 4.5),
    ("--cc-focus", "--cc-bg", 3.0),
    ("--cc-focus", "--cc-surface", 3.0),
    ("--cc-accent", "--cc-surface", 4.5),
    ("--cc-on-brand", "--cc-brand-strong", 4.5),
    ("--cc-text", "--cc-surface-sunk", 4.5),
    ("--cc-muted", "--cc-surface-sunk", 4.5),
    ("--cc-notice-text", "--cc-notice-bg", 4.5),
    ("--cc-free-text", "--cc-free-bg", 4.5),
    ("--cc-share-text", "--cc-share-bg", 4.5),
    ("--cc-share-text", "--cc-surface", 4.5),
    ("--cc-diet-text", "--cc-diet-bg", 4.5),
    ("--cc-allergen-text", "--cc-allergen-bg", 4.5),
    # Form components (phase 8a design pass): input borders are non-text UI (3:1, WCAG 1.4.11),
    # errors and the danger action are text.
    ("--cc-input-border", "--cc-surface", 3.0),
    ("--cc-input-border", "--cc-surface-sunk", 3.0),
    ("--cc-danger-text", "--cc-surface", 4.5),
    ("--cc-danger-text", "--cc-danger-bg", 4.5),
    ("--cc-text", "--cc-danger-bg", 4.5),
    ("--cc-danger-border", "--cc-danger-bg", 3.0),
    ("--cc-danger-border", "--cc-surface", 3.0),
    ("--cc-on-danger", "--cc-danger", 4.5),
    ("--cc-on-danger", "--cc-danger-strong", 4.5),
    ("--cc-accent", "--cc-surface-sunk", 3.0),
]


def test_ux_01_contrast_function_matches_known_values():
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast("#ffffff", "#a40408") == pytest.approx(8.08, abs=0.01)
    assert contrast("#777", "#777777") == pytest.approx(1.0)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_ux_01_token_pairs_meet_wcag_aa(theme):
    tokens = css_themes()[theme]
    failures = []
    for fg, bg, minimum in CONTRAST_PAIRS:
        ratio = contrast(tokens[fg], tokens[bg])
        if ratio < minimum:
            failures.append(f"{fg} on {bg}: {ratio:.2f} < {minimum}")
    assert failures == []


def test_ux_01_light_tokens_keep_the_2008_brand():
    light = css_themes()["light"]
    assert light["--cc-brand"] == "#a40408"
    assert light["--cc-bg"] == "#e5ecf3"


def test_ux_01_dark_theme_overrides_every_colour_token():
    sheet = css_themes()
    light_colours = {k for k, v in sheet["light"].items() if v.startswith("#")}
    text = APP_CSS.read_text(encoding="utf-8")
    dark_block = text[text.index("prefers-color-scheme: dark") :]
    missing = sorted(k for k in light_colours if f"{k}:" not in dark_block)
    assert missing == []


# --- LEG-09: UTF-8 and the copyright sign ------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("path", [*PUBLIC_PAGES, "/no-such-page"])
def test_leg_09_utf8_and_copyright_sign_in_footer(client, path):
    response = client.get(path)
    assert "charset=utf-8" in response["Content-Type"].lower()
    html = response.content.decode("utf-8")
    footer = html[html.index("<footer") : html.index("</footer>")]
    assert "©" in footer


# --- LEG-10: the 2008 typos stay fixed ---------------------------------------------------


@pytest.mark.django_db
def test_leg_10_home_and_seed_are_free_of_2008_typos(client):
    home = client.get("/").content.decode("utf-8")
    assert "ingredient" in home

    call_command("seed_demo")
    rows = MenuItem.objects.values_list("name", "description", "ingredients")
    seed_text = " ".join(" ".join(row) for row in rows)
    seed_text += " " + " ".join(CookProfile.objects.values_list("bio", flat=True))
    for text in (home, seed_text):
        for typo in ("ingredent", "Potatoe", "Macaronii"):
            assert not re.search(rf"\b{typo}\b", text), typo


# --- Static pages, steps and error pages -------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("path", PUBLIC_PAGES)
def test_public_pages_render_with_one_h1_noindex_and_help_links(client, path):
    response = client.get(path)
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert html.count("<h1") == 1
    assert '<meta name="robots" content="noindex, nofollow">' in html
    assert 'class="skip-link" href="#main"' in html
    for href in ('href="/how-it-works"', 'href="/safety"', 'href="/privacy"'):
        assert href in html
    assert "style=" not in html


@pytest.mark.django_db
def test_a11y_03a_home_steps_are_an_ordered_list_without_digit_images(client):
    html = client.get("/").content.decode("utf-8")
    steps = html[html.index('<ol class="steps"') : html.index("</ol>", html.index('<ol class="steps"'))]
    assert steps.count("<li") == 3
    headings = re.findall(r"<h3>([^<]+)</h3>", steps)
    assert headings == ["Register.", "Search.", "Eat!"]
    assert "<img" not in steps and "welcome1" not in html


@pytest.mark.django_db
def test_home_keeps_live_search_hooks_and_chip_in_line(client):
    html = client.get("/").content.decode("utf-8")
    assert 'id="q"' in html and 'id="results"' in html and 'aria-live="polite"' in html
    assert 'hx-target="#results"' in html
    assert "Cooks never make a profit." in html


@pytest.mark.django_db
def test_home_design_review_fixes(client):
    """Art-director fixes: no middle-dot strings in the listing card or the footer, no tracked
    eyebrows except the hero's, one filled button in the demo card, and a descriptive title."""
    html = client.get("/").content.decode("utf-8")
    ticket = html[html.index('<article class="ticket"') : html.index("</article>")]
    footer = html[html.index("<footer") : html.index("</footer>")]
    assert " · " not in ticket and " · " not in footer
    assert "Sat, 9:30, Breakfast" in ticket and "Marcus B., Larkspur State (Demo)" in ticket
    assert html.count('class="eyebrow"') == 1 and "step-kicker" not in html
    demo = html[html.index('class="demo-login') : html.index("</section>", html.index('class="demo-login'))]
    assert demo.count("btn-primary") == 1 and 'class="link-button">Try as demo cook' in demo
    assert "Campus Chefs · Home-cooked meals made by students" in html[: html.index("</title>")]
    assert "Cook's first name, dish or ingredient" in html


@pytest.mark.django_db
def test_safety_page_says_all_five_points_and_not_legal_advice(client):
    html = client.get("/safety").content.decode("utf-8")
    for phrase in (
        "cottage-food rules",
        "Allergens are self-declared",
        "severe allergy",
        "Nobody inspects the kitchens",
        "capped at the grocery cost",
        "sale of food",
        "This is not legal advice.",
    ):
        assert phrase in html, phrase


@pytest.mark.django_db
def test_privacy_page_lists_stored_and_never_stored_data_and_deletion(client):
    html = client.get("/privacy").content.decode("utf-8")
    for phrase in ("What we store", "What we never ask for", "Delete your account", "Former student", "Argon2id"):
        assert phrase in html, phrase


@pytest.mark.django_db
def test_how_it_works_has_step_anchors_and_chip_in_badges(client):
    html = client.get("/how-it-works").content.decode("utf-8")
    for anchor in ('id="register"', 'id="booking"'):
        assert anchor in html
    for badge in ("$4.00 grocery share per seat", "or bring an item", "Free"):
        assert badge in html


@pytest.mark.django_db
def test_custom_404_page(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    html = response.content.decode("utf-8")
    assert "This page is not on the menu." in html
    assert "Traceback" not in html


def test_leg_06b_500_page_is_generic():
    response = server_error(RequestFactory().get("/"))
    assert response.status_code == 500
    html = response.content.decode("utf-8")
    assert "Something went wrong in the kitchen." in html
    assert "©" in html
    for leak in ("Traceback", "psycopg", "Exception"):
        assert leak not in html


@pytest.mark.parametrize("name", ["logo.svg", "icon.svg"])
def test_svg_assets_have_a_title_and_no_script(name):
    svg = (ROOT / "static" / "img" / name).read_text(encoding="utf-8")
    assert re.search(r"<title[^>]*>Campus Chefs</title>", svg)
    assert "<script" not in svg and "href=" not in svg
