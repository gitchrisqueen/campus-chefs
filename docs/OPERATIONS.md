# Operations runbook

The demo runs locally with Docker Compose. All of its data is synthetic and disposable, and **there are no backups**: the reset for any problem is `docker compose down -v`, then `make demo`.

## Prerequisites

- Docker Engine with Compose v2. Phase 1 was tested on Engine 29.9.3 with Compose v5.7.0 (`docs/architecture.md`).
- `make`, `curl` and `jq`.
- About 3 GB of free disk space. The runtime image is 173 MB; the test image with Chromium is 1.92 GB.

## Everyday commands

| Task | Command |
|---|---|
| Start, or rebuild after a pull | `make demo` (runs `docker compose up -d --build`, then waits until `web` is healthy) |
| Open the app | http://127.0.0.1:8000 |
| Health check | `curl http://127.0.0.1:8000/healthz` prints `ok` |
| Follow the logs | `docker compose logs -f web` (also `migrate`, `db`, `keygen`) |
| Stop, keeping data | `docker compose down` |
| **Reset: wipe all data and secrets** | `docker compose down -v`, then `make demo` |
| Use another port | `WEB_PORT=8010 make demo` |
| Run the tests | `make test` (unit and integration), `make e2e NO_RESEED=1` (browser) |

## What starts, in order

1. `keygen` (one-shot, no network) generates the secrets on first run and gives each service only its own.
2. `db` (Postgres 18) starts on an internal network with no published port.
3. `migrate` (one-shot) runs `python manage.py bootstrap_demo`, which applies migrations and prepares the cache table.
4. `web` (gunicorn) starts only after `migrate` has exited 0, and listens on `127.0.0.1:8000`.

## When it breaks

| Symptom | Meaning | What to do |
|---|---|---|
| `curl …/healthz` prints `db unavailable` (HTTP 503) | `web` is up but cannot reach Postgres | Run `docker compose ps` and `docker compose logs db`. A `db` that is not healthy usually means a bad volume, so reset with `docker compose down -v` and `make demo` |
| `make demo` says `keygen exited with 1`, and the log says "DB data exists but its secrets are gone" | The `secrets-db` volume was removed while `pgdata` was kept, so the new passwords would not match the existing roles | Run `docker compose down -v`, then `make demo`. The data is synthetic |
| `make demo` says `migrate exited with …` | A migration or bootstrap step failed. `web` never starts, so nothing restarts in a loop | Read `docker compose logs migrate keygen`. Fix the code or reset with `docker compose down -v` |
| `make demo` times out waiting for `web` | `web` started but never became healthy | Read `docker compose logs --tail 50 web`. The entrypoint prints which secret file is missing, if any |
| Port 8000 is in use | Another process holds the port | Run `WEB_PORT=8010 make demo` |
| CI fails on "Public-safety denylist" for a pull request from a fork | Fork PRs cannot read the `PUBLIC_DENYLIST_REGEX` secret, so the step fails closed on purpose | A maintainer re-runs the change from a branch in this repository |

## Rollback

The demo has no deploy target (plan decision D5). Rolling back means checking out the previous commit and resetting:

```sh
git checkout <previous-sha>
docker compose down -v
make demo
```
