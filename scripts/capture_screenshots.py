"""Capture documentation screenshots with Playwright Chromium.

Run it inside the `tests` container (the repo is mounted read-only at /src; only
test-results/ and docs/screenshots/ are writable):

    docker compose --profile test run --rm tests python scripts/capture_screenshots.py --before

--before  Screenshots the statically rendered 2008 landing page. Run
          legacy-support/render-static.sh first. The page is opened through
          file:// so the relative ../css and ../img paths resolve. No server runs.
          Output: docs/screenshots/before/welcome.png (desktop, 1280 px wide) and
          docs/screenshots/before/welcome-phone.png (phone, 390 px wide).

Each mode is a function registered in MODES, so phase 11 can add an "after" mode
by adding one function and one entry. It is not implemented here.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Browser, sync_playwright

REPO = Path(__file__).resolve().parent.parent
RENDERED_WELCOME = REPO / "test-results" / "legacy-render" / "view" / "welcome.html"
SHOTS = REPO / "docs" / "screenshots"

DESKTOP = {"width": 1280, "height": 900}
PHONE = {"width": 390, "height": 844}


def shoot_before(browser: Browser) -> list[Path]:
    """Desktop and phone screenshots of the rendered 2008 welcome page."""
    if not RENDERED_WELCOME.is_file():
        sys.exit(f"missing {RENDERED_WELCOME}: run legacy-support/render-static.sh first")
    out_dir = SHOTS / "before"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, viewport in (("welcome.png", DESKTOP), ("welcome-phone.png", PHONE)):
        context = browser.new_context(viewport=viewport, device_scale_factor=1)
        page = context.new_page()
        page.goto(RENDERED_WELCOME.as_uri())
        page.wait_for_load_state("load")
        target = out_dir / name
        # full_page keeps the whole 2008 layout, including any horizontal overflow
        # at phone width, which is part of what the screenshot shows.
        page.screenshot(path=str(target), full_page=True)
        context.close()
        written.append(target)
    return written


# Mode flag -> function. Phase 11 adds "after" here.
MODES: dict[str, Callable[[Browser], list[Path]]] = {
    "before": shoot_before,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    for mode in MODES:
        group.add_argument(f"--{mode}", dest="mode", action="store_const", const=mode)
    args = parser.parse_args(argv)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            written = MODES[args.mode](browser)
        finally:
            browser.close()
    for path in written:
        print(path.relative_to(REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
