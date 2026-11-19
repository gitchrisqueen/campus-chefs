import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_auth_09_tampered_csrf_token_gives_403_and_no_login(page, base_url):
    page.goto(f"{base_url}/login")
    login_form = page.locator('main form[action="/login"]')
    login_form.locator('input[name="username"]').fill("diner@larkspur.example")
    login_form.locator('input[name="password"]').fill("not-the-password-123")
    login_form.locator('input[name="csrfmiddlewaretoken"]').evaluate("el => { el.value = 'x'.repeat(64) }")

    with page.expect_response(lambda r: r.url.endswith("/login") and r.request.method == "POST") as info:
        login_form.locator('button[type="submit"]').click()
    assert info.value.status == 403
    expect(page.locator("body")).to_contain_text("CSRF verification failed")

    page.goto(f"{base_url}/me")
    assert "/login?next=/me" in page.url


def test_auth_10_no_request_url_carries_a_password(page, base_url):
    urls: list[str] = []
    page.on("request", lambda r: urls.append(r.url))
    page.goto(f"{base_url}/login")
    login_form = page.locator('main form[action="/login"]')
    login_form.locator('input[name="username"]').fill("diner@larkspur.example")
    login_form.locator('input[name="password"]').fill("not-the-password-123")
    with page.expect_response(lambda r: r.url.endswith("/login") and r.request.method == "POST"):
        login_form.locator('button[type="submit"]').click()
    page.goto(f"{base_url}/register")
    page.goto(f"{base_url}/me")
    assert len(urls) >= 4
    assert [u for u in urls if "password" in u.lower()] == []
