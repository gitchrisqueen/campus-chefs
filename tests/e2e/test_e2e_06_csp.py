import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

RECORD_CSP = (
    "window.__csp = [];"
    "document.addEventListener('securitypolicyviolation',"
    " e => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));"
)


def test_e2e_06_no_csp_violations_and_htmx_live_search(page, base_url):
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script(RECORD_CSP)

    page.goto(f"{base_url}/")
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
    paths = {"/"} | {h.split("#")[0] for h in hrefs if h.startswith("/") and not h.startswith("/admin")}
    for path in sorted(p for p in paths if p):
        page.goto(f"{base_url}{path}")
        assert page.evaluate("window.__csp") == [], f"CSP violation on {path}"

    # The home search box runs the real search (meals.search) and swaps in offering cards.
    page.goto(f"{base_url}/")
    page.fill("#q", "pancakes")
    expect(page.locator("#results")).to_contain_text("Buttermilk Pancakes")
    expect(page.locator("#results")).to_contain_text("not a safety guarantee")
    assert page.url.rstrip("/") == base_url, "live search must swap in place, not navigate"

    # The /search filters update #results in place too.
    page.goto(f"{base_url}/search")
    page.fill("#q", "pancakes")
    expect(page.locator("#results .offer-card").first).to_contain_text("Buttermilk Pancakes")
    page.check("#exclude_2")  # fish: pancakes stay
    page.check("#exclude_6")  # wheat: pancakes go
    expect(page.locator("#results")).to_contain_text("No meals match")
    assert page.url == f"{base_url}/search", "filters must swap in place, not navigate"
    assert page.evaluate("window.__csp") == []
    assert errors == []
