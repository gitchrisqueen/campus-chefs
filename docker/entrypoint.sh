#!/bin/sh
# Fail fast with a clear message when a mounted secret is missing.
set -eu
for var in DJANGO_SECRET_KEY_FILE DB_PASSWORD_FILE; do
  eval "path=\${${var}:-}"
  if [ -n "${path}" ] && [ ! -r "${path}" ]; then
    echo "entrypoint: ${var} points to ${path}, which is missing or unreadable" >&2
    exit 1
  fi
done
exec "$@"
