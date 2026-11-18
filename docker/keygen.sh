#!/bin/sh
# One-shot secret generator (plan 6.2). Runs with no network.
# - Guard: if DB data exists but its secrets are gone, stop (OPS-02).
# - Generate each missing secret once (80 hex chars).
# - Distribute on every run, atomically, one volume per consumer:
#     /out/db    -> db container (uid 70): superuser, owner and app passwords
#     /out/owner -> migrate/tests (uid 10001): django key, owner password
#     /out/web   -> web (uid 10001): django key, app password
set -eu

gen() { od -An -tx1 -N40 /dev/urandom | tr -d ' \n'; }

put() { # put <src-or-dash> <dest> <uid>
  tmp="$2.tmp.$$"
  if [ "$1" = "-" ]; then gen > "${tmp}"; else cp "$1" "${tmp}"; fi
  chmod 0400 "${tmp}"
  chown "$3:$3" "${tmp}"
  mv -f "${tmp}" "$2"
}

missing=0
for f in db_superuser_password db_owner_password db_app_password; do
  [ -s "/out/db/${f}" ] || missing=1
done
if [ "${missing}" = 1 ] && [ -f /pgdata/18/docker/PG_VERSION ]; then
  echo "keygen: DB data exists but its secrets are gone. Run: docker compose down -v (demo data is synthetic)" >&2
  exit 1
fi

for f in db_superuser_password db_owner_password db_app_password; do
  [ -s "/out/db/${f}" ] || put - "/out/db/${f}" 70
done
[ -s /out/owner/django_secret_key ] || put - /out/owner/django_secret_key 10001

put /out/db/db_owner_password /out/owner/db_owner_password 10001
put /out/db/db_app_password /out/web/db_app_password 10001
put /out/owner/django_secret_key /out/web/django_secret_key 10001
echo "keygen: secrets ready"
