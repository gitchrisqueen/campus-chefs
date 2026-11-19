"""Partial coverage of plan tests whose full versions land in later phases.

A letter suffix (SEC-03a) marks the part of a plan test that phase 1 can already prove;
the owning phase adds the rest under the plain ID.
"""

import pytest
from django.core.management import call_command
from django.db import OperationalError, connection
from django.utils import timezone

from accounts.models import User
from tests import factories as f


@pytest.fixture
def db_unreachable(monkeypatch):
    """Every connection attempt fails the way psycopg does when Postgres is down."""

    def refuse():
        raise OperationalError('psycopg.OperationalError: connection to server at "db" failed: Connection refused')

    monkeypatch.setattr(connection, "ensure_connection", refuse)


def test_leg_06_db_unreachable_gives_503_healthz_and_generic_500_page(client, settings, db_unreachable):
    """The 2008 site printed the raw MySQL error. Now /healthz says 503 and pages show the 500 page."""
    health = client.get("/healthz")
    assert health.status_code == 503
    assert health.content == b"db unavailable"

    # A returning visitor has a session cookie, so / must read the session table and fails there.
    client.raise_request_exception = False
    client.cookies[settings.SESSION_COOKIE_NAME] = "a" * 32
    home = client.get("/")
    assert home.status_code == 500
    html = home.content.decode("utf-8")
    assert "Something went wrong in the kitchen." in html
    for leak in (b"psycopg", b"Traceback", b"OperationalError", b"Connection refused"):
        assert leak not in home.content and leak not in health.content


def test_sec_03a_robots_disallows_everything(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.content == b"User-agent: *\nDisallow: /\n"


@pytest.mark.django_db
def test_sec_03a_every_page_is_noindex(client):
    assert b'<meta name="robots" content="noindex, nofollow">' in client.get("/").content


@pytest.mark.django_db(transaction=True)
def test_ops_01a_bootstrap_demo_is_idempotent():
    call_command("bootstrap_demo")
    call_command("bootstrap_demo")
    tables = connection.introspection.table_names()
    assert "cc_ratelimit" in tables
    assert "accounts_user" in tables


@pytest.mark.django_db
def test_auth_00a_user_manager_normalizes_email_and_sets_flags():
    campus = f.campus()
    now = timezone.now()
    user = User.objects.create_user(
        "Ava.R@LARKSPUR.example",
        "a-long-test-password-1",
        first_name="Ava",
        last_name="Reyes",
        campus=campus,
        adult_attested_at=now,
    )
    assert user.email == "Ava.R@larkspur.example"
    assert str(user) == "Ava.R@larkspur.example"
    assert not user.is_staff and not user.is_superuser
    assert user.check_password("a-long-test-password-1")
    assert user.password.startswith("argon2$argon2id$")

    admin = User.objects.create_superuser(
        "admin@larkspur.example",
        "another-long-password-2",
        first_name="Ada",
        last_name="Min",
        campus=campus,
        adult_attested_at=now,
    )
    assert user.public_name == "Ava R."
    assert admin.is_staff and admin.is_superuser

    with pytest.raises(ValueError):
        User.objects.create_user("", "x")
