import pytest
from django.db import connection
from django.test import Client

from core.ratelimit import MAX_FAILURES, WINDOW_SECONDS
from tests import factories as f

PASSWORD = "a-long-test-password-1"
EMAIL = "ava.r@larkspur.example"
INCORRECT = b"Email or password is incorrect"


@pytest.fixture
def ava(db):
    return f.user(first="Ava", email=EMAIL, password=PASSWORD)


def _logged_in_id(client):
    return client.session.get("_auth_user_id")


@pytest.mark.django_db
def test_auth_01_login_redirects_to_me_and_cycles_session_key(client, ava):
    before = client.session.session_key
    response = client.post("/login", {"username": EMAIL, "password": PASSWORD})
    assert response.status_code == 302
    assert response["Location"] == "/me"
    assert int(_logged_in_id(client)) == ava.pk
    assert client.session.session_key != before


@pytest.mark.django_db
def test_auth_01_login_is_case_insensitive_and_honours_safe_next(client, ava):
    response = client.post("/login", {"username": EMAIL.upper(), "password": PASSWORD, "next": "/me/edit"})
    assert response["Location"] == "/me/edit"


@pytest.mark.django_db
def test_auth_01_login_ignores_offsite_next(client, ava):
    response = client.post("/login", {"username": EMAIL, "password": PASSWORD, "next": "https://evil.example/"})
    assert response["Location"] == "/me"


@pytest.mark.django_db
def test_auth_02_wrong_password_and_unknown_email_get_the_same_message(client, ava):
    wrong = client.post("/login", {"username": EMAIL, "password": "not-the-password-1"})
    unknown = client.post("/login", {"username": "nobody@larkspur.example", "password": PASSWORD})
    for response in (wrong, unknown):
        assert response.status_code == 200
        assert INCORRECT in response.content
    assert _logged_in_id(client) is None


@pytest.mark.django_db
def test_auth_02_inactive_account_gets_the_same_message(client, ava):
    ava.is_active = False
    ava.save()
    response = client.post("/login", {"username": EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    assert INCORRECT in response.content


@pytest.mark.django_db
def test_auth_03_credentials_in_query_string_do_not_log_in(client, ava):
    response = client.get("/login", {"email": EMAIL, "password": PASSWORD, "username": EMAIL})
    assert response.status_code == 200
    assert b'method="post"' in response.content
    assert _logged_in_id(client) is None


@pytest.mark.django_db
def test_auth_04_login_without_csrf_token_is_403(ava):
    client = Client(enforce_csrf_checks=True)
    response = client.post("/login", {"username": EMAIL, "password": PASSWORD})
    assert response.status_code == 403
    assert _logged_in_id(client) is None


def _cache_keys():
    with connection.cursor() as cursor:
        cursor.execute("SELECT cache_key FROM cc_ratelimit")
        return [row[0] for row in cursor.fetchall()]


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/login", "/admin/login/"])
def test_auth_05_five_failures_lock_the_email_for_15_minutes(client, url):
    f.user(email=EMAIL, password=PASSWORD, is_staff=True)
    for _ in range(MAX_FAILURES):
        response = client.post(url, {"username": EMAIL, "password": "wrong-password-123"})
        assert response.status_code == 200
    response = client.post(url, {"username": EMAIL.upper(), "password": PASSWORD})
    assert response.status_code == 429
    assert response["Retry-After"] == str(WINDOW_SECONDS)
    assert _logged_in_id(client) is None

    keys = _cache_keys()
    assert len(keys) == 1
    assert "@" not in keys[0] and "ava" not in keys[0].lower()


@pytest.mark.django_db
def test_auth_05_success_below_the_limit_resets_the_count(client, ava):
    for _ in range(MAX_FAILURES - 1):
        client.post("/login", {"username": EMAIL, "password": "wrong-password-123"})
    assert client.post("/login", {"username": EMAIL, "password": PASSWORD}).status_code == 302
    assert _cache_keys() == []
    assert client.get("/login").status_code == 200


@pytest.mark.django_db
def test_auth_06_logout_is_post_only(client, ava):
    client.force_login(ava)
    assert client.get("/logout").status_code == 405
    assert int(_logged_in_id(client)) == ava.pk
    response = client.post("/logout")
    assert response.status_code == 302
    assert _logged_in_id(client) is None


@pytest.mark.django_db
def test_auth_06_logout_with_csrf_enforced(ava):
    client = Client(enforce_csrf_checks=True)
    client.force_login(ava)
    page = client.get("/me")
    token = page.context["csrf_token"]
    assert client.post("/logout", {"csrfmiddlewaretoken": str(token)}).status_code == 302
    assert _logged_in_id(client) is None


@pytest.mark.django_db
def test_auth_08_me_requires_login(client):
    response = client.get("/me")
    assert response.status_code == 302
    assert response["Location"] == "/login?next=/me"


@pytest.mark.django_db
def test_auth_11_password_change_keeps_this_session_and_ends_the_others(ava):
    this, other = Client(), Client()
    assert this.login(username=EMAIL, password=PASSWORD)
    assert other.login(username=EMAIL, password=PASSWORD)
    new = "a-brand-new-password-2"

    rejected = this.post(
        "/me/password", {"old_password": "wrong-password-123", "new_password1": new, "new_password2": new}
    )
    assert rejected.status_code == 200
    ava.refresh_from_db()
    assert ava.check_password(PASSWORD)
    assert this.get("/me").status_code == 200
    assert other.get("/me").status_code == 200

    changed = this.post("/me/password", {"old_password": PASSWORD, "new_password1": new, "new_password2": new})
    assert changed.status_code == 302
    assert changed["Location"] == "/me"
    ava.refresh_from_db()
    assert ava.check_password(new)
    assert this.get("/me").status_code == 200
    assert other.get("/me").status_code == 302


def _fullwidth(text: str) -> str:
    """ASCII letters and digits as their fullwidth forms, which NFKC folds back to ASCII."""
    return "".join(chr(ord(c) + 0xFEE0) if c.isascii() and c.isalnum() else c for c in text)


@pytest.mark.django_db
def test_auth_05_unicode_equivalent_emails_share_one_counter(client, ava):
    """Security review: NFKC-equivalent spellings authenticate as one account, so they must share a key."""
    variant = _fullwidth(EMAIL)
    assert variant != EMAIL
    for _ in range(MAX_FAILURES):
        assert client.post("/login", {"username": variant, "password": "wrong-password-123"}).status_code == 200
    response = client.post("/login", {"username": EMAIL, "password": PASSWORD})
    assert response.status_code == 429
    assert _logged_in_id(client) is None


@pytest.mark.django_db
def test_auth_05_mixed_spellings_trigger_the_limit(client, ava):
    spellings = [EMAIL, EMAIL.upper(), _fullwidth(EMAIL), f"  {EMAIL}  ", _fullwidth(EMAIL.upper())]
    assert len(spellings) == MAX_FAILURES
    for spelling in spellings:
        client.post("/login", {"username": spelling, "password": "wrong-password-123"})
    assert client.post("/login", {"username": EMAIL, "password": PASSWORD}).status_code == 429


@pytest.mark.django_db
def test_auth_05_lockout_is_logged_without_the_email(client, ava, caplog):
    for _ in range(MAX_FAILURES):
        client.post("/login", {"username": EMAIL, "password": "wrong-password-123"})
    with caplog.at_level("WARNING", logger="core.ratelimit"):
        assert client.post("/login", {"username": EMAIL, "password": PASSWORD}).status_code == 429
    messages = [r.getMessage() for r in caplog.records if r.name == "core.ratelimit"]
    assert len(messages) == 1
    assert "login locked" in messages[0]
    assert "@" not in messages[0] and "ava" not in messages[0].lower()


@pytest.mark.django_db
def test_auth_05_cache_failure_fails_open_and_logs(client, ava, caplog, monkeypatch):
    """If the limiter's cache table is unavailable, login still works and the error is logged."""
    from django.core.cache import caches

    def boom(*args, **kwargs):
        raise RuntimeError("cache table missing")

    cache = caches["ratelimit"]
    monkeypatch.setattr(cache, "get", boom)
    monkeypatch.setattr(cache, "set", boom)
    monkeypatch.setattr(cache, "delete", boom)
    with caplog.at_level("ERROR", logger="core.ratelimit"):
        response = client.post("/login", {"username": EMAIL, "password": PASSWORD})
    assert response.status_code == 302
    assert any("rate limiter unavailable" in r.getMessage() for r in caplog.records)
