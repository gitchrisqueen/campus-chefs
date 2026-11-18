"""Capture design-review screenshots of the running demo with Playwright.

Run inside the tests container, which has Chromium and can reach the web service:

    docker compose --profile test run --rm tests python scripts/capture_screenshots.py --design

--design saves full-page PNGs of /, /how-it-works and /safety at 1280 px and 390 px wide,
in light and dark mode, plus the live search with results, to docs/screenshots/design/.
It also checks each page for CSP violations and for horizontal scroll at 320 px,
and exits 1 if it finds either.
"""

import argparse
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DESIGN_PAGES = {"home": "/", "how-it-works": "/how-it-works", "safety": "/safety"}
WIDTHS = {"desktop": (1280, 800), "phone": (390, 844)}
SCHEMES = ["light", "dark"]
RECORD_CSP = (
    "window.__csp = [];"
    "document.addEventListener('securitypolicyviolation',"
    " e => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));"
)


def capture_design(base_url: str, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for scheme in SCHEMES:
            for label, (width, height) in WIDTHS.items():
                context = browser.new_context(
                    viewport={"width": width, "height": height}, color_scheme=scheme, device_scale_factor=1
                )
                context.add_init_script(RECORD_CSP)
                page = context.new_page()
                for name, path in DESIGN_PAGES.items():
                    page.goto(f"{base_url}{path}", wait_until="networkidle")
                    if page.evaluate("window.__csp"):
                        problems.append(f"CSP violation on {path} ({scheme}, {label})")
                    target = out / f"{name}-{label}-{scheme}.png"
                    page.screenshot(path=str(target), full_page=True)
                    print(target.relative_to(ROOT))
                # The live search with results swapped in by htmx.
                page.goto(f"{base_url}/", wait_until="networkidle")
                page.fill("#q", "che")
                page.locator("#results li").first.wait_for()
                page.locator("#search").scroll_into_view_if_needed()
                target = out / f"home-search-{label}-{scheme}.png"
                page.screenshot(path=str(target))
                print(target.relative_to(ROOT))
                context.close()

        context = browser.new_context(viewport={"width": 320, "height": 800})
        page = context.new_page()
        for path in DESIGN_PAGES.values():
            page.goto(f"{base_url}{path}", wait_until="networkidle")
            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            if scroll_width > 320:
                problems.append(f"horizontal scroll on {path} at 320 px: scrollWidth={scroll_width}")
        context.close()
        browser.close()
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--design", action="store_true", help="capture the design-review set")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "screenshots" / "design")
    args = parser.parse_args()
    if not args.design:
        parser.error("choose a capture set, for example --design")
    return capture_design(args.base_url.rstrip("/"), args.out)


if __name__ == "__main__":
    sys.exit(main())
