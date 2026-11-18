import re

import pytest

# Tests visit this path on purpose to check the 404 page; Chromium logs the 404 as a console error.
EXPECTED_404 = re.compile(r"^\S+/no-such-page: Failed to load resource: .* 404 ")


@pytest.fixture
def new_page(browser):
    """Open pages in fresh browser contexts and fail the test on any console error (plan 7.1).

    Chromium reports each CSP violation as a console error ("Refused to ..."), so this listener
    also catches a blocked inline script or style. Usage: `page = new_page(java_script_enabled=False)`.
    """
    opened: list[tuple] = []

    def make(**context_args):
        context = browser.new_context(**context_args)
        page = context.new_page()
        errors: list[str] = []
        page.on("console", lambda m: errors.append(f"{page.url}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"{page.url}: {e}"))
        opened.append((context, errors))
        return page

    yield make
    problems = [error for _, errors in opened for error in errors if not EXPECTED_404.match(error)]
    for context, _ in opened:
        context.close()
    assert problems == [], problems
