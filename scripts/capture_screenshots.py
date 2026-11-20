"""Capture screenshots of the running demo with Playwright.

Run inside the tests container, which has Chromium and can reach the web service:

    docker compose --profile test run --rm tests python scripts/capture_screenshots.py --design

--design saves full-page PNGs at 1280 px and 390 px wide, in light and dark mode, to
docs/screenshots/design/:
- the public pages: /, /how-it-works, /safety, /login and /register;
- the live search with results, and /register submitted empty (the error state);
- /me as the demo diner and as the demo cook, each reached by clicking its "Try as demo ..." button;
- /me/edit, /me/password and /me/delete as the demo diner;
- the search page with results, the cook page and an offering (public);
- the offering with its booking form (and that form submitted empty), and a booking, as the demo diner;
- the kitchen, the offering with its diners list, and the same booking, as the demo cook.
Run `make reseed` first, so the bookings look as seeded.
It also checks each page for CSP violations and for horizontal scroll at 320 px,
and exits 1 if it finds either.

Next to the PNGs it writes the files the art director (reviewer O) reads, one key per capture
("<page>-<phone|desktop>-<light|dark>"):
- styles.json: the computed font-family, font-size, font-weight, color, background-color,
  letter-spacing and text-transform of body, h1, h2, help, meta and small text, labels, buttons,
  links, badges and the eyebrow (the first visible one of each), plus every text colour and
  background as hex, the font families, the body size, the smallest text size and the longest
  paragraph in characters;
- layout.json: the viewport width, document scrollWidth, a horizontal-overflow boolean, the
  elements past the right edge, and the filled buttons visible in the first screen (the fold);
- manifest.json, written last: the capture list with "complete": true and "styled" (false if
  a page loaded without app.css applied). It is removed when a run starts, so a folder without
  it is an unfinished capture.

--before screenshots the statically rendered original landing page (run
legacy-support/render-static.sh first). It opens the file through file:// so the
relative ../css and ../img paths resolve; no server runs. Output:
docs/screenshots/before/welcome.png (1280 px) and welcome-phone.png (390 px).

--after saves the README and walkthrough screenshots of the seeded demo to
docs/screenshots/after/, in light mode. It only reads pages, so a second run on the same seed
on the same day writes the same pictures. Run `make reseed` first.
- Full-page at 1280 px: home, search, cook, offering (the demo diner's booking form with the
  grocery share picked), booking (the diner's confirmed Steak Night booking), me (the diner's
  dashboard) and kitchen-menu (the demo cook's kitchen).
- The first screen at 390 px, saved at 2x: phone-home, phone-search, phone-offering,
  phone-booking and phone-kitchen.

--walkthrough plays the two halves of the booking story, E2E-01 and E2E-02, and saves one
1120 x 700 picture per step to docs/screenshots/walkthrough/ (01-home.png to 14-review-on-cook-page.png).
docs/walkthrough.md shows them in order. It books a seat, confirms it, marks a share received,
completes a booking and posts a review, so run `make reseed` before and after it.
scripts/build-hero-gif.sh joins pictures 02, 04, 05 and 08 into docs/screenshots/after/hero.gif (it plays
once) and pictures 01 to 08 into docs/screenshots/after/booking-loop.gif (it loops; the README links to it).
`make screenshots` runs the whole sequence.

Playwright writes PNGs with no EXIF, XMP or text chunks; scripts/check-image-metadata.sh checks
every image under docs/screenshots.
"""

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DESIGN_PAGES = {
    "home": "/",
    "how-it-works": "/how-it-works",
    "safety": "/safety",
    "login": "/login",
    "register": "/register",
    "search": "/search?q=pancakes",
    "cook": "{cook}",
    "offering": "{offering}",
}
# Captured after the demo login; the diner also gets the three account forms. The {names} are
# filled in from the seed: the Pancake Breakfast offering, its cook, and the diner's Steak Night booking.
PERSONA_PAGES = {
    "diner": {
        "me-diner": "/me",
        "edit": "/me/edit",
        "password": "/me/password",
        "delete": "/me/delete",
        "offering-diner": "{offering}",
        "booking-diner": "{booking}",
    },
    "cook": {"me-cook": "/me", "kitchen": "/kitchen", "offering-cook": "{offering}", "booking-cook": "{booking}"},
}
WIDTHS = {"desktop": (1280, 800), "phone": (390, 844)}
SCHEMES = ["light", "dark"]
MANIFEST_VERSION = 1
# The first visible element of each role is described in styles.json.
STYLE_ROLES = {
    "body": "body",
    "h1": "main h1",
    "h2": "main h2",
    "help": "main .field-help, main .hint",
    "meta": "main .offer-meta, main .ticket-meta span, main .chip-in span, main .cook-entry span, main .muted",
    "small": "main .small",
    "meal_type": "main .offer-kind",
    "label": "main .facts dt, main .summary dt, main .field-label",
    "button_primary": "main .btn-primary",
    "button_secondary": "main .btn-secondary",
    "link": "main a:not(.btn)",
    "nav_link": ".site-nav a",
    "badge": "main .badge",
    "eyebrow": "main .eyebrow",
}
STYLE_PROPS = [
    "font-family",
    "font-size",
    "font-weight",
    "color",
    "background-color",
    "letter-spacing",
    "text-transform",
]
# Runs in the page: computed styles per role, page-wide colours and sizes, and the layout facts.
PROBE = r"""
([roles, props]) => {
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const visible = (el) => {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && cs.visibility !== 'hidden' && cs.display !== 'none' && cs.opacity !== '0';
  };
  const label = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
    (el.classList.length ? '.' + Array.from(el.classList).slice(0, 2).join('.') : '');
  const styles = {};
  for (const [role, selector] of Object.entries(roles)) {
    const el = Array.from(document.querySelectorAll(selector)).find(visible);
    if (!el) { styles[role] = null; continue; }
    const cs = getComputedStyle(el);
    styles[role] = {element: label(el), text: el.textContent.trim().split(/\s+/).slice(0, 8).join(' ')};
    for (const prop of props) styles[role][prop] = cs.getPropertyValue(prop);
  }
  const colors = new Set(), families = new Set(), overflow = [];
  let longest = 0, smallest = null;
  for (const el of document.body.querySelectorAll('*')) {
    if (!visible(el)) continue;
    const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    if (Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim())) {
      colors.add(cs.color);
      families.add(cs.fontFamily.split(',')[0].replace(/["']/g, '').trim());
      const fs = parseFloat(cs.fontSize);
      smallest = smallest === null ? fs : Math.min(smallest, fs);
      if (/^(P|LI|DD)$/.test(el.tagName)) longest = Math.max(longest, Math.round(r.width / (fs * 0.5)));
    }
    if (cs.backgroundColor !== 'rgba(0, 0, 0, 0)') colors.add(cs.backgroundColor);
    if (r.right > vw + 1 && cs.position !== 'fixed') overflow.push(label(el));
  }
  const fold = Array.from(document.querySelectorAll('.btn-primary')).filter(el => {
    const r = el.getBoundingClientRect();
    return visible(el) && r.top < vh && r.bottom > 0;
  }).map(el => el.textContent.trim().replace(/\s+/g, ' '));
  const sheets = Array.from(document.styleSheets).filter(sh => /\/css\/app(\.[0-9a-f]+)?\.css$/.test(sh.href || ''));
  const styled = sheets.some(sh => { try { return sh.cssRules.length > 0; } catch (e) { return false; } });
  const scrollWidth = document.documentElement.scrollWidth;
  return {
    styles, styled,
    colors: Array.from(colors), font_families: Array.from(families).filter(Boolean).sort(),
    body_font_px: parseFloat(getComputedStyle(document.body).fontSize),
    smallest_text_px: smallest, longest_paragraph_chars_est: longest,
    layout: {viewport_width: vw, viewport_height: vh, scroll_width: scrollWidth,
             horizontal_overflow: scrollWidth > vw, overflowing: overflow.slice(0, 50),
             fold_filled_buttons: fold},
  };
}
"""
RECORD_CSP = (
    "window.__csp = [];"
    "document.addEventListener('securitypolicyviolation',"
    " e => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));"
)


def to_hex(css: str) -> str:
    """'rgb(164, 4, 8)' -> '#a40408'; with alpha below 1, two more hex digits. Anything else unchanged."""
    if not css.startswith("rgb"):
        return css
    parts = [p.strip() for p in css[css.index("(") + 1 : css.rindex(")")].replace("/", ",").split(",") if p.strip()]
    r, g, b = (round(float(x)) for x in parts[:3])
    alpha = f"{round(float(parts[3]) * 255):02x}" if len(parts) > 3 and float(parts[3]) < 1 else ""
    return f"#{r:02x}{g:02x}{b:02x}{alpha}"


class Record:
    """What one design run collects for styles.json, layout.json and manifest.json."""

    def __init__(self) -> None:
        self.captures: list[dict] = []
        self.styles: dict[str, dict] = {}
        self.layout: dict[str, dict] = {}
        self.styled = True

    def probe(self, page, key: str, png: str, full_page: bool) -> None:
        facts = page.evaluate(PROBE, [STYLE_ROLES, STYLE_PROPS])
        for described in facts["styles"].values():
            if described:
                for prop in ("color", "background-color"):
                    described[f"{prop}-hex"] = to_hex(described[prop])
        self.styled = self.styled and facts["styled"]
        self.styles[key] = {
            "roles": facts["styles"],
            "colors": sorted({to_hex(c) for c in facts["colors"]}),
            "font_families": facts["font_families"],
            "body_font_px": facts["body_font_px"],
            "smallest_text_px": facts["smallest_text_px"],
            "longest_paragraph_chars_est": facts["longest_paragraph_chars_est"],
        }
        self.layout[key] = facts["layout"]
        self.captures.append({"key": key, "file": png, "url": page.url, "full_page": full_page})

    def write(self, out: Path, base_url: str) -> None:
        for name, data in (("styles.json", self.styles), ("layout.json", self.layout)):
            (out / name).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        manifest = {
            "url": base_url,
            "at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "viewports": [f"{w}x{h}" for w, h in WIDTHS.values()],
            "themes": SCHEMES,
            "version": MANIFEST_VERSION,
            "complete": True,
            "styled": self.styled,
            "blocked_hosts": {},
            "captures": self.captures,
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")


def _shoot(page, out: Path, name: str, problems: list[str], where: str, record: Record) -> None:
    if page.evaluate("window.__csp"):
        problems.append(f"CSP violation on {page.url} ({where})")
    target = out / f"{name}.png"
    page.screenshot(path=str(target), full_page=True)
    record.probe(page, name, target.name, full_page=True)
    print(target.relative_to(ROOT))


def _seeded_paths(browser, base_url: str) -> dict[str, str]:
    """Find the seeded pages whose ids change on every reseed."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{base_url}/search?q=pancakes", wait_until="networkidle")
    card = page.locator(".offer-card", has_text="Pancake Breakfast")
    paths = {
        "offering": card.locator(".offer-title a").get_attribute("href"),
        "cook": card.locator(".offer-cook a").get_attribute("href"),
    }
    page.goto(f"{base_url}/login", wait_until="networkidle")
    page.get_by_role("button", name="Try as demo diner").click()
    page.wait_for_url(f"{base_url}/me")
    paths["booking"] = page.get_by_role("link", name="Steak Night").get_attribute("href")
    context.close()
    return paths


def capture_design(base_url: str, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").unlink(missing_ok=True)  # written last, only by a finished run
    problems: list[str] = []
    record = Record()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        seeded = _seeded_paths(browser, base_url)
        for scheme in SCHEMES:
            for label, (width, height) in WIDTHS.items():
                context = browser.new_context(
                    viewport={"width": width, "height": height}, color_scheme=scheme, device_scale_factor=1
                )
                context.add_init_script(RECORD_CSP)
                page = context.new_page()
                where = f"{scheme}, {label}"
                for name, path in DESIGN_PAGES.items():
                    page.goto(f"{base_url}{path.format(**seeded)}", wait_until="networkidle")
                    _shoot(page, out, f"{name}-{label}-{scheme}", problems, where, record)
                # The register form submitted empty: the error summary and the field errors.
                page.goto(f"{base_url}/register", wait_until="networkidle")
                page.locator('main form[action="/register"] button[type="submit"]').click()
                page.wait_for_load_state("networkidle")
                _shoot(page, out, f"register-errors-{label}-{scheme}", problems, where, record)
                # The live search with results swapped in by htmx.
                page.goto(f"{base_url}/", wait_until="networkidle")
                page.fill("#q", "che")
                page.locator("#results li").first.wait_for()
                page.locator("#search").scroll_into_view_if_needed()
                target = out / f"home-search-{label}-{scheme}.png"
                page.screenshot(path=str(target))
                record.probe(page, target.stem, target.name, full_page=False)
                print(target.relative_to(ROOT))
                context.close()

                # Each persona in a fresh context, logged in by its demo button on the home page.
                for persona, pages in PERSONA_PAGES.items():
                    context = browser.new_context(
                        viewport={"width": width, "height": height}, color_scheme=scheme, device_scale_factor=1
                    )
                    context.add_init_script(RECORD_CSP)
                    page = context.new_page()
                    page.goto(f"{base_url}/", wait_until="networkidle")
                    page.get_by_role("button", name=f"Try as demo {persona}").click()
                    page.wait_for_url(f"{base_url}/me")
                    for name, path in pages.items():
                        page.goto(f"{base_url}{path.format(**seeded)}", wait_until="networkidle")
                        _shoot(page, out, f"{name}-{label}-{scheme}", problems, where, record)
                    if persona == "diner":
                        # The booking form submitted without the allergen box: its error state.
                        page.goto(f"{base_url}{seeded['offering']}", wait_until="networkidle")
                        page.locator('.booking-form button[type="submit"]').click()
                        page.locator(".booking-form .error-summary").wait_for()
                        _shoot(page, out, f"offering-errors-{label}-{scheme}", problems, where, record)
                    context.close()

        # No horizontal scroll at 320 px: the public pages, then each persona's pages.
        def check_320(page, path: str) -> None:
            page.goto(f"{base_url}{path}", wait_until="networkidle")
            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            if scroll_width > 320:
                problems.append(f"horizontal scroll on {path} at 320 px: scrollWidth={scroll_width}")

        for persona, pages in {"visitor": DESIGN_PAGES, **PERSONA_PAGES}.items():
            context = browser.new_context(viewport={"width": 320, "height": 800})
            page = context.new_page()
            if persona != "visitor":
                page.goto(f"{base_url}/login", wait_until="networkidle")
                page.get_by_role("button", name=f"Try as demo {persona}").click()
                page.wait_for_url(f"{base_url}/me")
            for path in pages.values():
                check_320(page, path.format(**seeded))
            context.close()
        browser.close()
    record.write(out, base_url)
    if not record.styled:
        problems.append("a page loaded without app.css applied (manifest styled: false)")
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


def capture_before() -> int:
    """Desktop and phone screenshots of the statically rendered original welcome page."""
    rendered = ROOT / "test-results" / "legacy-render" / "view" / "welcome.html"
    if not rendered.is_file():
        sys.exit(f"missing {rendered}: run legacy-support/render-static.sh first")
    out_dir = ROOT / "docs" / "screenshots" / "before"
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for name, viewport in (("welcome.png", (1280, 900)), ("welcome-phone.png", (390, 844))):
                context = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
                page = context.new_page()
                page.goto(rendered.as_uri())
                page.wait_for_load_state("load")
                # full_page keeps the whole fixed-width layout, including its overflow on a phone.
                page.screenshot(path=str(out_dir / name), full_page=True)
                context.close()
                print((out_dir / name).relative_to(ROOT))
        finally:
            browser.close()
    return 0


AFTER_DESKTOP = (1280, 800)
AFTER_PHONE = (390, 844)
HERO_VIEWPORT = (1120, 700)
REVIEWED_COOK = "Tess W."
# Scrolls an element to the start, centre or end of the screen; start and end keep a 16 px margin.
SCROLL_TO = """(el, block) => {
  el.scrollIntoView({block});
  window.scrollBy(0, block === 'start' ? -16 : block === 'end' ? 16 : 0);
}"""
# Phone captures show one screen; these scroll to the part the picture is about.
PHONE_SCROLL = {
    "phone-search": ("#results", "start"),
    "phone-offering": ("#booking-panel", "end"),
}


def _login(page, base_url: str, persona: str) -> None:
    page.goto(f"{base_url}/login", wait_until="networkidle")
    page.get_by_role("button", name=f"Try as demo {persona}").click()
    page.wait_for_url(f"{base_url}/me")


def _pick_share_and_ack(page) -> None:
    """Fill the booking form without sending it: one seat, the grocery share, the allergen box."""
    form = page.locator(".booking-form")
    form.get_by_role("radio", name="Grocery share: ", exact=False).check()
    form.locator("#id_allergen_ack").check()


def capture_after(base_url: str, out: Path) -> int:
    """The eight named README screenshots plus the phone set. Reads pages only."""
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        seeded = _seeded_paths(browser, base_url)
        # The demo cook has no reviews until E2E-02 runs, so the cook picture uses a seeded cook
        # whose page has reviews and whose meals are at fixed hours. Search matches first names.
        page = browser.new_page()
        page.goto(f"{base_url}/search?q={REVIEWED_COOK.split()[0]}", wait_until="networkidle")
        seeded["reviewed_cook"] = page.locator(".offer-cook a", has_text=REVIEWED_COOK).first.get_attribute("href")
        page.close()

        def shots(persona: str | None, phone: bool, pages: dict[str, str]) -> None:
            width, height = AFTER_PHONE if phone else AFTER_DESKTOP
            context = browser.new_context(
                viewport={"width": width, "height": height},
                color_scheme="light",
                device_scale_factor=2 if phone else 1,
                reduced_motion="reduce",
            )
            page = context.new_page()
            if persona:
                _login(page, base_url, persona)
            for name, path in pages.items():
                page.goto(f"{base_url}{path.format(**seeded)}", wait_until="networkidle")
                if "offering" in name and persona == "diner":
                    _pick_share_and_ack(page)
                    page.locator("#id_allergen_ack").blur()
                if phone and name in PHONE_SCROLL:
                    # The first screen of a phone would show only the page top, so scroll to the subject.
                    selector, block = PHONE_SCROLL[name]
                    page.locator(selector).evaluate(SCROLL_TO, block)
                page.screenshot(path=str(out / f"{name}.png"), full_page=not phone)
                print((out / f"{name}.png").relative_to(ROOT))
            context.close()

        shots(None, False, {"home": "/", "search": "/search?q=pancakes", "cook": seeded["reviewed_cook"]})
        shots("diner", False, {"offering": "{offering}", "booking": "{booking}", "me": "/me"})
        shots("cook", False, {"kitchen-menu": "/kitchen"})
        shots(None, True, {"phone-home": "/", "phone-search": "/search?q=pancakes"})
        shots("diner", True, {"phone-offering": "{offering}", "phone-booking": "{booking}"})
        shots("cook", True, {"phone-kitchen": "/kitchen"})
        browser.close()
    return 0


def capture_walkthrough(base_url: str, out: Path) -> int:
    """One picture per step of E2E-01 and E2E-02. Writes data: see the module docstring."""
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    width, height = HERO_VIEWPORT
    count = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        def open_as(persona: str | None):
            context = browser.new_context(
                viewport={"width": width, "height": height},
                color_scheme="light",
                device_scale_factor=1,
                reduced_motion="reduce",
            )
            page = context.new_page()
            if persona:
                _login(page, base_url, persona)
            return page

        def frame(page, label: str, show: str | None = None, block: str = "center") -> None:
            """Save the current screen. `show` is a selector to scroll into view first."""
            nonlocal count
            if show:
                page.locator(show).first.evaluate(SCROLL_TO, block)
            count += 1
            target = out / f"{count:02d}-{label}.png"
            page.screenshot(path=str(target))
            print(target.relative_to(ROOT))

        # --- E2E-01: a diner finds a meal, picks the grocery share and asks for a seat; the cook confirms.
        visitor = open_as(None)
        visitor.goto(f"{base_url}/", wait_until="networkidle")
        frame(visitor, "home")

        # The live search on the home page: htmx swaps the results in under the box.
        diner = open_as("diner")
        steak_night = diner.get_by_role("link", name="Steak Night").get_attribute("href")
        diner.goto(f"{base_url}/", wait_until="networkidle")
        diner.locator("#q").press_sequentially("pancakes")
        card = diner.locator("#results .offer-card", has_text="Pancake Breakfast")
        card.wait_for()
        diner.wait_for_load_state("networkidle")
        diner.locator("#search").evaluate(SCROLL_TO, "start")
        frame(diner, "search")

        card.get_by_role("link", name="Pancake Breakfast").click()
        diner.wait_for_load_state("networkidle")
        frame(diner, "offering")

        _pick_share_and_ack(diner)
        frame(diner, "form", show="#booking-panel")

        diner.locator('.booking-form button[type="submit"]').click()
        panel = diner.locator("#booking-panel")
        panel.get_by_role("link", name="View your booking").wait_for()
        booking = panel.get_by_role("link", name="View your booking").get_attribute("href")
        frame(diner, "request-sent", show="#booking-panel")

        cook = open_as("cook")
        cook.goto(f"{base_url}{booking}", wait_until="networkidle")
        frame(cook, "cook-sees-request", show='section[aria-labelledby="actions-heading"]', block="end")
        cook.get_by_role("button", name="Confirm").click()
        cook.locator(".messages").get_by_text("Booking confirmed.").wait_for()
        frame(cook, "cook-confirmed")

        diner.goto(f"{base_url}{booking}", wait_until="networkidle")
        frame(diner, "diner-confirmed")

        # --- E2E-02: after the meal the cook marks the share received and the booking completed;
        # the diner reviews it. Uses the seeded Steak Night booking, served yesterday.
        cook.goto(f"{base_url}{steak_night}", wait_until="networkidle")
        frame(cook, "cook-after-the-meal")
        cook.get_by_role("button", name="Mark contribution received").click()
        cook.locator(".messages").get_by_text("Contribution marked received.").wait_for()
        frame(cook, "share-received")
        cook.get_by_role("button", name="Mark completed").click()
        cook.locator(".messages").get_by_text("Booking marked completed.").wait_for()
        frame(cook, "completed")

        diner.goto(f"{base_url}{steak_night}", wait_until="networkidle")
        review = diner.locator('form[action$="/review"]')
        review.get_by_label("5 stars").check()
        review.get_by_label("The good").fill("Steak cooked just right, and the herb butter was great.")
        review.get_by_label("The bad").fill("Pickup ran ten minutes late.")
        review.get_by_label("The bad").blur()
        frame(diner, "review-form", show='section[aria-labelledby="review-heading"]', block="end")
        review.get_by_role("button", name="Post review").click()
        diner.locator(".messages").get_by_text("Thanks, your review is posted.").wait_for()
        frame(diner, "review-posted")

        diner.locator(".page-head").get_by_role("link").click()  # the cook's public page
        diner.wait_for_load_state("networkidle")
        frame(diner, "review-on-cook-page", show=".review-list")
        browser.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--design", action="store_true", help="capture the design-review set")
    parser.add_argument("--before", action="store_true", help="capture the rendered original landing page")
    parser.add_argument("--after", action="store_true", help="capture the README screenshots")
    parser.add_argument("--walkthrough", action="store_true", help="capture each step of E2E-01 and E2E-02")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--out", type=Path, help="output folder (each capture set has its own default)")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    if args.before:
        return capture_before()
    if args.after:
        return capture_after(base_url, args.out or ROOT / "docs" / "screenshots" / "after")
    if args.walkthrough:
        return capture_walkthrough(base_url, args.out or ROOT / "docs" / "screenshots" / "walkthrough")
    if not args.design:
        parser.error("choose a capture set: --design, --before, --after or --walkthrough")
    return capture_design(base_url, args.out or ROOT / "docs" / "screenshots" / "design")


if __name__ == "__main__":
    sys.exit(main())
