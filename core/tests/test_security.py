import os
import shutil
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest
from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory

from core.secrets import read_secret

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.django_db
def test_sec_01_security_headers_and_session_cookie_flags(client):
    response = client.get("/")
    csp = response["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp
    assert "script-src 'self'" in csp
    assert "default-src 'self'" in csp
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "same-origin"
    assert response["X-Frame-Options"] == "DENY"
    assert "geolocation=()" in response["Permissions-Policy"]

    # The real Set-Cookie written by SessionMiddleware when a session changes.
    request = RequestFactory().get("/")
    middleware = SessionMiddleware(lambda req: HttpResponse("ok"))
    middleware.process_request(request)
    request.session["probe"] = 1
    set_cookie = middleware.process_response(request, HttpResponse("ok")).cookies[settings.SESSION_COOKIE_NAME]
    assert set_cookie["httponly"] is True
    assert set_cookie["samesite"] == "Lax"


def _app_role_connection():
    user = os.environ.get("DB_APP_USER")
    password = read_secret("DB_APP_PASSWORD")
    if not (user and password):
        if os.environ.get("CC_REQUIRE_ROLE_TESTS") == "1":
            pytest.fail("CC_REQUIRE_ROLE_TESTS=1 but DB_APP_USER/DB_APP_PASSWORD are not set")
        pytest.skip("app-role credentials not available")
    db = settings.DATABASES["default"]
    return psycopg.connect(
        host=db["HOST"], port=db["PORT"], dbname=db["NAME"], user=user, password=password, connect_timeout=3
    )


def test_sec_04_app_role_is_not_superuser_or_createdb():
    with _app_role_connection() as conn:
        row = conn.execute("SELECT rolsuper, rolcreatedb FROM pg_roles WHERE rolname = current_user").fetchone()
    assert row == (False, False)


def test_sec_05_app_role_cannot_create_tables():
    with _app_role_connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("CREATE TABLE sec05_probe(i int)")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.test", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _denylist(repo: Path, regex: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PUBLIC_DENYLIST_REGEX": regex}
    return subprocess.run(["bash", "scripts/denylist.sh"], cwd=repo, env=env, capture_output=True, text=True)


def test_sec_06_denylist_reports_locations_never_matches(tmp_path):
    if not shutil.which("git"):
        pytest.fail("git is required for SEC-06")
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "scripts" / "denylist.sh", repo / "scripts" / "denylist.sh")
    (repo / "clean.txt").write_text("nothing to see\n")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    token = "zq-planted-token-7731"

    clean = _denylist(repo, token)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert "0 findings" in clean.stdout

    empty = _denylist(repo, "")
    assert empty.returncode != 0

    # Planted in a commit, then deleted: the history scan must still find it.
    (repo / "notes.txt").write_text(f"line one\nhello {token} world\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "plant")
    _git(repo, "rm", "-q", "notes.txt")
    _git(repo, "commit", "-qm", "remove")
    hit = _denylist(repo, token)
    assert hit.returncode == 1
    assert ":notes.txt:2" in hit.stdout
    assert token not in hit.stdout + hit.stderr


def test_sec_09_local_http_refused_for_non_loopback_hosts():
    env = {**os.environ, "CC_DEMO_LOCAL_HTTP": "true", "DJANGO_ALLOWED_HOSTS": "campuschefs.example"}
    env.setdefault("DJANGO_SECRET_KEY", "sec09-dummy-key-not-a-secret")
    bad = subprocess.run(
        [sys.executable, "-c", "import config.settings"], cwd=ROOT, env=env, capture_output=True, text=True
    )
    assert bad.returncode != 0
    assert "ImproperlyConfigured" in bad.stderr

    env["DJANGO_ALLOWED_HOSTS"] = "127.0.0.1,localhost,web"
    ok = subprocess.run(
        [sys.executable, "-c", "import config.settings"], cwd=ROOT, env=env, capture_output=True, text=True
    )
    assert ok.returncode == 0, ok.stderr
