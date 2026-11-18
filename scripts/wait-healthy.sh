#!/usr/bin/env bash
# Usage: scripts/wait-healthy.sh <service> <timeout-seconds>
# Polls `docker compose ps` until <service> is healthy. Fails early if keygen
# or migrate exited non-zero, and prints their logs.
set -euo pipefail
svc="${1:?service}"; timeout="${2:-180}"; waited=0

state() { # state <service> -> "<State> <Health> <ExitCode>"
  docker compose ps -a --format json "$1" 2>/dev/null \
    | jq -rs 'map(select(.Service == "'"$1"'")) | .[0] // {} | "\(.State // "none") \(if (.Health // "") == "" then "-" else .Health end) \(.ExitCode // 0)"'
}

while :; do
  for oneshot in keygen migrate; do
    read -r st _ code <<<"$(state "${oneshot}")"
    if [ "${st}" = "exited" ] && [ "${code}" != "0" ]; then
      echo "wait-healthy: ${oneshot} exited with ${code}" >&2
      docker compose logs --no-color "${oneshot}" | tail -20 >&2
      exit 1
    fi
  done
  read -r st health _ <<<"$(state "${svc}")"
  if [ "${health}" = "healthy" ]; then echo "wait-healthy: ${svc} healthy after ${waited}s"; exit 0; fi
  if [ "${waited}" -ge "${timeout}" ]; then
    echo "wait-healthy: ${svc} not healthy after ${timeout}s (state=${st} health=${health})" >&2
    docker compose logs --no-color --tail 30 "${svc}" >&2 || true
    exit 1
  fi
  sleep 2; waited=$((waited + 2))
done
