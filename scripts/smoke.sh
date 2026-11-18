#!/usr/bin/env bash
# Smoke checks against the running compose stack (plan 8.1).
#   scripts/smoke.sh base  -> checks 1-5 (phase 1)
#   scripts/smoke.sh       -> checks 1-7 (6 and 7 need seed data, phase 2)
set -euo pipefail
section="${1:-all}"
base="http://127.0.0.1:${WEB_PORT:-8000}"
pass() { echo "smoke: PASS $1"; }
fail() { echo "smoke: FAIL $1" >&2; exit 1; }

# 1. health and home page
[ "$(curl -fsS "${base}/healthz")" = "ok" ] || fail "1 /healthz != ok"
curl -fsS "${base}/" | grep -q "Campus Chefs" || fail "1 / lacks 'Campus Chefs'"
pass "1 healthz ok, home renders"

# 2. a POST without a CSRF token is rejected
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "${base}/")"
[ "${code}" = "403" ] || fail "2 POST without CSRF returned ${code}, expected 403"
pass "2 CSRF enforced (403)"

# 3. web does not run as root
uid="$(docker compose exec -T web id -u)"
[ "${uid}" != "0" ] || fail "3 web runs as uid 0"
pass "3 web uid=${uid}"

# 4. SEC-08 secret isolation
web_secrets="$(docker compose exec -T web ls /run/cc-secrets | tr '\n' ' ')"
[ "${web_secrets}" = "db_app_password django_secret_key " ] || fail "4 web secrets: ${web_secrets}"
mig_secrets="$(docker compose run --rm --no-deps -T migrate ls /run/cc-secrets | tr '\n' ' ')"
[ "${mig_secrets}" = "db_owner_password django_secret_key " ] || fail "4 migrate secrets: ${mig_secrets}"
pass "4 SEC-08 web and migrate see only their own secrets"

# 5. the web DB role is not a superuser
rolsuper="$(docker compose exec -T web python -c '
import django; django.setup()
from django.db import connection
with connection.cursor() as c:
    c.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
    print(c.fetchone()[0])')"
[ "${rolsuper}" = "False" ] || fail "5 rolsuper=${rolsuper}"
pass "5 web DB role rolsuper=false"

[ "${section}" = "base" ] && { echo "smoke: base checks passed"; exit 0; }

# 6 and 7 arrive in phase 2 with seed_demo.
fail "6-7 not implemented until phase 2; run 'scripts/smoke.sh base'"
