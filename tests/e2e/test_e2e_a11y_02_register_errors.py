import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_a11y_02_empty_register_focuses_summary_and_links_each_error(page, base_url):
    page.goto(f"{base_url}/register")
    page.locator('main form[action="/register"] button[type="submit"]').click()

    summary = page.locator(".error-summary")
    expect(summary).to_be_visible()
    expect(summary).to_be_focused()

    invalid = page.locator('main form [aria-invalid="true"]')
    assert invalid.count() > 0
    for i in range(invalid.count()):
        control = invalid.nth(i)
        if control.get_attribute("type") == "radio":
            # A radio group carries aria-describedby on its fieldset (Django's use_fieldset).
            described_by = control.evaluate("el => el.closest('fieldset').getAttribute('aria-describedby')")
        else:
            described_by = control.get_attribute("aria-describedby")
        assert described_by, control.get_attribute("name")
        error_ids = [i for i in described_by.split() if i.endswith("_error")]
        assert error_ids, described_by
        expect(page.locator(f"#{error_ids[0]}")).not_to_be_empty()
