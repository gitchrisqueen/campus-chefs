"""Capture design-review screenshots of the running demo with Playwright.

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

--before screenshots the statically rendered original landing page (run
legacy-support/render-static.sh first). It opens the file through file:// so the
relative ../css and ../img paths resolve; no server runs. Output:
docs/screenshots/before/welcome.png (1280 px) and welcome-phone.png (390 px).
"""

import argparse
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
RECORD_CSP = (
    "window.__csp = [];"
    "document.addEventListener('securitypolicyviolation',"
    " e => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));"
)


def _shoot(page, out: Path, name: str, problems: list[str], where: str) -> None:
    if page.evaluate("window.__csp"):
        problems.append(f"CSP violation on {page.url} ({where})")
    target = out / f"{name}.png"
    page.screenshot(path=str(target), full_page=True)
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
    problems: list[str] = []
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
                    _shoot(page, out, f"{name}-{label}-{scheme}", problems, where)
                # The register form submitted empty: the error summary and the field errors.
                page.goto(f"{base_url}/register", wait_until="networkidle")
                page.locator('main form[action="/register"] button[type="submit"]').click()
                page.wait_for_load_state("networkidle")
                _shoot(page, out, f"register-errors-{label}-{scheme}", problems, where)
                # The live search with results swapped in by htmx.
                page.goto(f"{base_url}/", wait_until="networkidle")
                page.fill("#q", "che")
                page.locator("#results li").first.wait_for()
                page.locator("#search").scroll_into_view_if_needed()
                target = out / f"home-search-{label}-{scheme}.png"
                page.screenshot(path=str(target))
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
                        _shoot(page, out, f"{name}-{label}-{scheme}", problems, where)
                    if persona == "diner":
                        # The booking form submitted without the allergen box: its error state.
                        page.goto(f"{base_url}{seeded['offering']}", wait_until="networkidle")
                        page.locator('.booking-form button[type="submit"]').click()
                        page.locator(".booking-form .error-summary").wait_for()
                        _shoot(page, out, f"offering-errors-{label}-{scheme}", problems, where)
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--design", action="store_true", help="capture the design-review set")
    parser.add_argument("--before", action="store_true", help="capture the rendered original landing page")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "screenshots" / "design")
    args = parser.parse_args()
    if args.before:
        return capture_before()
    if not args.design:
        parser.error("choose a capture set: --design or --before")
    return capture_design(args.base_url.rstrip("/"), args.out)


if __name__ == "__main__":
    sys.exit(main())
