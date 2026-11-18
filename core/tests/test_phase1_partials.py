"""Partial coverage of plan tests whose full versions land in later phases.

A letter suffix (LEG-06a) marks the part of a plan test that phase 1 can already prove;
the owning phase adds the rest under the plain ID.
"""

import pytest
from django.core.management import call_command
from django.db import OperationalError, connection

from accounts.models import User


def test_leg_06a_healthz_503_when_db_unreachable(client, monkeypatch):
    def boom():
        raise OperationalError("connection refused")

    monkeypatch.setattr(connection, "ensure_connection", boom)
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.content == b"db unavailable"
    assert b"psycopg" not in response.content and b"Traceback" not in response.content


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
def test_e2e_06a_search_stub_partial_for_htmx_full_page_without_js(client):
    partial = client.get("/search/stub", {"q": "toast"}, headers={"HX-Request": "true"})
    assert b"French Toast" in partial.content
    assert b"<html" not in partial.content

    full = client.get("/search/stub", {"q": "toast"})
    assert b"French Toast" in full.content
    assert b"<html" in full.content

    none = client.get("/search/stub", {"q": "zzz"}, headers={"HX-Request": "true"})
    assert "No dishes match “zzz”.".encode() in none.content


@pytest.mark.django_db
def test_auth_00a_user_manager_normalizes_email_and_sets_flags():
    user = User.objects.create_user("Ava.R@LARKSPUR.example", "a-long-test-password-1")
    assert user.email == "Ava.R@larkspur.example"
    assert str(user) == "Ava.R@larkspur.example"
    assert not user.is_staff and not user.is_superuser
    assert user.check_password("a-long-test-password-1")
    assert user.password.startswith("argon2$argon2id$")

    admin = User.objects.create_superuser("admin@larkspur.example", "another-long-password-2")
    assert admin.is_staff and admin.is_superuser

    with pytest.raises(ValueError):
        User.objects.create_user("", "x")
