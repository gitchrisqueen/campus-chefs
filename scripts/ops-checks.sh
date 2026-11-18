#!/usr/bin/env bash
# Ops checks (plan 7.4). THEY DESTROY LOCAL DEMO DATA (docker compose down -v).
# Usage: scripts/ops-checks.sh ops_01 ops_02 ops_03   (no args = all)
set -euo pipefail
cd "$(dirname "$0")/.."
checks=("$@"); [ "${#checks[@]}" -gt 0 ] || checks=(ops_01 ops_02 ops_03)
pass() { echo "ops: PASS $1"; }
fail() { echo "ops: FAIL $1" >&2; exit 1; }

ops_01() { # seeded data persists across down/up without -v
  local before after code
  make demo >/dev/null
  before="$(docker compose exec -T web python -c 'import django; django.setup()
from meals.models import Offering; print(Offering.objects.count())')"
  docker compose down >/dev/null 2>&1
  make demo >/dev/null
  after="$(docker compose exec -T web python -c 'import django; django.setup()
from meals.models import Offering; print(Offering.objects.count())')"
  code="$(docker compose ps -a --format json migrate | jq -rs '.[0].ExitCode')"
  [ "${before}" -ge 10 ] && [ "${before}" = "${after}" ] || fail "OPS-01 offerings ${before} -> ${after}"
  [ "${code}" = "0" ] || fail "OPS-01 migrate exit=${code}"
  pass "OPS-01 ${after} offerings persisted across down/up, migrate exit 0"
}

ops_02() { # losing the secrets volume with data present fails loudly, and down -v recovers
  make demo >/dev/null
  docker compose down >/dev/null 2>&1
  docker volume rm -f "${COMPOSE_PROJECT_NAME:-campuschefs}_secrets-db" >/dev/null
  docker compose up -d >/dev/null 2>&1 || true
  sleep 3
  docker compose logs --no-color keygen | grep -q "secrets are gone" || fail "OPS-02 keygen message missing"
  code="$(docker compose ps -a --format json keygen | jq -rs '.[0].ExitCode')"
  [ "${code}" = "1" ] || fail "OPS-02 keygen exit=${code}, expected 1"
  docker compose down -v >/dev/null 2>&1
  make demo >/dev/null || fail "OPS-02 recovery after down -v"
  pass "OPS-02 keygen guard (exit 1 + message), recovered with down -v"
}

ops_03() { # CSRF works on a non-default published port with no CSRF_TRUSTED_ORIGINS
  local port=8010 jar token code pw
  WEB_PORT="${port}" docker compose up -d >/dev/null 2>&1
  WEB_PORT="${port}" scripts/wait-healthy.sh web 120 >/dev/null
  # A throwaway account with a random password (the seeded personas have unusable passwords).
  pw="$(od -An -tx1 -N16 /dev/urandom | tr -d ' \n')"
  docker compose exec -T -e OPS03_PASSWORD="${pw}" web python -c 'import os, django; django.setup()
from django.utils import timezone
from accounts.models import User
from meals.models import Campus
user, _ = User.objects.get_or_create(email="ops03@ops-check.example", defaults={
    "first_name": "Ops", "last_name": "Check", "campus": Campus.objects.first(), "adult_attested_at": timezone.now()})
user.set_password(os.environ["OPS03_PASSWORD"])
user.save()' || fail "OPS-03 could not create the check account"
  jar="$(mktemp)"
  token="$(curl -fsS -c "${jar}" "http://127.0.0.1:${port}/login" \
    | sed -n 's/.*name="csrfmiddlewaretoken" value="\([^"]*\)".*/\1/p' | head -1)"
  [ -n "${token}" ] || fail "OPS-03 no CSRF token on /login"
  code="$(curl -s -o /dev/null -w '%{http_code}' -b "${jar}" -c "${jar}" \
    -H "Origin: http://127.0.0.1:${port}" -H "Referer: http://127.0.0.1:${port}/login" \
    --data-urlencode "csrfmiddlewaretoken=${token}" --data-urlencode "username=ops03@ops-check.example" \
    --data-urlencode "password=${pw}" "http://127.0.0.1:${port}/login")"
  rm -f "${jar}"
  [ "${code}" = "302" ] || fail "OPS-03 POST /login with token on port ${port} returned ${code} (403 = CSRF origin failure)"
  docker compose up -d >/dev/null 2>&1 && scripts/wait-healthy.sh web 120 >/dev/null
  pass "OPS-03 CSRF passes on port ${port} (POST /login logged in, 302)"
}

for c in "${checks[@]}"; do
  case "${c}" in
    ops_01|ops_02|ops_03) "${c}" ;;
    *) fail "unknown check ${c}" ;;
  esac
done
