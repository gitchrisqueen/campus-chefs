#!/usr/bin/env bash
# Ops checks (plan 7.4). THEY DESTROY LOCAL DEMO DATA (docker compose down -v).
# Usage: scripts/ops-checks.sh ops_02 ops_03   (no args = all implemented checks)
set -euo pipefail
cd "$(dirname "$0")/.."
checks=("$@"); [ "${#checks[@]}" -gt 0 ] || checks=(ops_02 ops_03)
pass() { echo "ops: PASS $1"; }
fail() { echo "ops: FAIL $1" >&2; exit 1; }

ops_02() { # losing the secrets volume with data present fails loudly, and down -v recovers
  make demo >/dev/null
  docker compose down >/dev/null 2>&1
  docker volume rm -f campuschefs_secrets-db >/dev/null
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
  local port=8010 jar token code
  WEB_PORT="${port}" docker compose up -d >/dev/null 2>&1
  WEB_PORT="${port}" scripts/wait-healthy.sh web 120 >/dev/null
  jar="$(mktemp)"
  # Phase 1 target: the admin login form. Phase 3 switches to /login and expects 302.
  token="$(curl -fsS -c "${jar}" "http://127.0.0.1:${port}/admin/login/" \
    | sed -n 's/.*name="csrfmiddlewaretoken" value="\([^"]*\)".*/\1/p' | head -1)"
  [ -n "${token}" ] || fail "OPS-03 no CSRF token on login form"
  code="$(curl -s -o /dev/null -w '%{http_code}' -b "${jar}" -c "${jar}" \
    -H "Origin: http://127.0.0.1:${port}" -H "Referer: http://127.0.0.1:${port}/admin/login/" \
    --data-urlencode "csrfmiddlewaretoken=${token}" --data-urlencode "username=nobody@example.test" \
    --data-urlencode "password=wrong-password-123" "http://127.0.0.1:${port}/admin/login/")"
  rm -f "${jar}"
  [ "${code}" = "200" ] || fail "OPS-03 POST with token on port ${port} returned ${code} (403 = CSRF origin failure)"
  docker compose up -d >/dev/null 2>&1 && scripts/wait-healthy.sh web 120 >/dev/null
  pass "OPS-03 CSRF passes on port ${port} (login form re-rendered, 200)"
}

for c in "${checks[@]}"; do
  case "${c}" in
    ops_02|ops_03) "${c}" ;;
    ops_01) fail "OPS-01 needs seed data (phase 2)" ;;
    *) fail "unknown check ${c}" ;;
  esac
done
