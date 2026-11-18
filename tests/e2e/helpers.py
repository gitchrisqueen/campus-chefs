"""Shared helpers for the browser tests (plan 7.1).

The tests run against a running stack at BASE_URL (the root conftest's `base_url` fixture):
`http://web:8000` from the tests container, `http://127.0.0.1:8000` from the CI runner.
`make e2e` reseeds the demo data first, so each run starts from the same seed.
"""

import uuid
from pathlib import Path

AXE_JS = Path(__file__).resolve().parent / "vendor" / "axe.min.js"
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]

# Reports each violation as "rule-id (impact): help -> first targets", so a failure names the fix.
AXE_RUN = """async (tags) => {
  const result = await axe.run(document, {runOnly: {type: "tag", values: tags}, resultTypes: ["violations"]});
  return result.violations.map(v =>
    `${v.id} (${v.impact}): ${v.help} -> ` + v.nodes.slice(0, 4).map(n => n.target.join(" ")).join(" | "));
}"""


def axe_violations(page) -> list[str]:
    """Run the vendored axe-core on the current page and return its violations.

    `page.evaluate` runs through the DevTools protocol, which the page's CSP does not govern, so
    axe is injected without an inline script and without relaxing the app's CSP.
    """
    if not page.evaluate("typeof window.axe !== 'undefined'"):
        page.evaluate(AXE_JS.read_text(encoding="utf-8"))
    return page.evaluate(AXE_RUN, AXE_TAGS)


def demo_login(page, base_url: str, persona: str) -> None:
    """Log in as the demo diner or cook with the "Try as demo ..." button on /login."""
    page.goto(f"{base_url}/login")
    page.get_by_role("button", name=f"Try as demo {persona}").click()
    page.wait_for_url(f"{base_url}/me")


def unique_email(prefix: str) -> str:
    """A synthetic address that is new on every run (the `.example` domain never resolves)."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}@e2e.example"
