"""Browser-side regressions for 2008 defects (plan 1.3, 7.2): LEG-07 and LEG-08.

The original site shipped "Under Construction" placeholders and header and footer links to pages
that did not exist. These tests crawl the rebuilt site as a visitor, the demo diner and the
demo cook. GET requests only: every state change in the app is a POST form, never a link.
"""

import re
from collections import deque
from urllib.parse import urljoin, urlsplit

import pytest

from tests.e2e.helpers import demo_login

pytestmark = pytest.mark.e2e

HREF = re.compile(r'<a\b[^>]*\bhref="([^"]+)"')
CRAWL_LIMIT = 150
CHROME_LINKS = "header a[href], nav a[href], footer a[href]"


def _same_site_paths(html: str, current: str, base_url: str) -> set[str]:
    paths = set()
    for href in HREF.findall(html):
        url = urljoin(current, href.replace("&amp;", "&"))
        parts = urlsplit(url)
        if f"{parts.scheme}://{parts.netloc}" != base_url or parts.path.startswith("/admin"):
            continue
        paths.add(parts.path + (f"?{parts.query}" if parts.query else ""))
    return paths


def _crawl(request, base_url: str) -> dict[str, str]:
    """Breadth-first crawl from / and /me; returns {path: html} for every 200 HTML page."""
    seen, pages = set(), {}
    queue = deque(["/", "/me", "/kitchen", "/search?q=pancakes"])
    while queue and len(seen) < CRAWL_LIMIT:
        path = queue.popleft()
        if path in seen:
            continue
        seen.add(path)
        response = request.get(f"{base_url}{path}")
        if response.status != 200 or "text/html" not in response.headers.get("content-type", ""):
            continue
        html = response.text()
        pages[path] = html
        queue.extend(sorted(_same_site_paths(html, response.url, base_url) - seen))
    return pages


@pytest.mark.parametrize("persona", ["visitor", "diner", "cook"])
def test_leg_07_no_page_says_under_construction(page, base_url, persona):
    if persona != "visitor":
        demo_login(page, base_url, persona)
    pages = _crawl(page.context.request, base_url)
    assert len(pages) >= 8, sorted(pages)
    offenders = [path for path, html in pages.items() if re.search(r"under\s+construction", html, re.I)]
    assert offenders == []


@pytest.mark.parametrize("persona", ["visitor", "diner", "cook"])
def test_leg_08_every_header_nav_and_footer_link_returns_200(page, base_url, persona):
    if persona != "visitor":
        demo_login(page, base_url, persona)
    links: set[str] = set()
    for path in ("/", "/search", "/how-it-works", "/me", "/login"):
        page.goto(f"{base_url}{path}")
        hrefs = page.eval_on_selector_all(CHROME_LINKS, "els => els.map(e => e.href)")
        links |= {href.split("#")[0] for href in hrefs}
    assert {f"{base_url}/how-it-works", f"{base_url}/safety", f"{base_url}/privacy"} <= links
    statuses = {url: page.context.request.get(url, max_redirects=0).status for url in sorted(links)}
    assert {url: status for url, status in statuses.items() if status != 200} == {}
