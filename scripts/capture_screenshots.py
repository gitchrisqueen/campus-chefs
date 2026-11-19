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
