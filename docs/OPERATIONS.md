# Operations runbook

The demo runs locally with Docker Compose. Seeded offerings are timed relative to the first boot, so a volume kept for more than a week runs out of future meals: run `make reseed`. All of its data is synthetic and disposable, and **there are no backups**: the reset for any problem is `docker compose down -v`, then `make demo`.

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
| Reseed the demo data | `make reseed` wipes and recreates the synthetic data, timed relative to now. It runs in one transaction, so a failure part-way leaves the old data in place. Staff accounts and their campuses are kept |
| Check the seeded data | `docker compose exec web python manage.py shell -c "from meals.models import Offering; from bookings.models import Booking, Review; print(Offering.objects.count(), Booking.objects.count(), Review.objects.count())"` prints `16 26 12` on a fresh seed |
| Run the tests | `make test` (unit and integration), `make e2e` (browser; reseeds first) |

## Admin account

No staff account is seeded, and the demo personas have no password, so they cannot log in to the admin.

1. List the campus ids:
   `docker compose exec web python manage.py shell -c "from meals.models import Campus; print(list(Campus.objects.values_list('id', 'name')))"`.
   The ids change after a reseed, except for campuses that a staff account belongs to.
2. Create the account: `docker compose run --rm migrate python manage.py createsuperuser`. It asks for email, first name, last name, a campus id and a password. For a scripted run, add `-e DJANGO_SUPERUSER_PASSWORD=...` and `--noinput --email ... --first_name ... --last_name ... --campus <id>`.
3. Sign in at http://127.0.0.1:8000/admin/.

## What starts, in order

1. `keygen` (one-shot, no network) generates the secrets on first run and gives each service only its own.
2. `db` (Postgres 18) starts on an internal network with no published port.
3. `migrate` (one-shot) runs `python manage.py bootstrap_demo`. It applies migrations, prepares the cache table, clears expired sessions and, on a fresh database with `CC_DEMO_MODE=true` (the compose default), seeds the synthetic demo data.
4. `web` (gunicorn) starts only after `migrate` has exited 0, and listens on `127.0.0.1:8000`.

## When it breaks

| Symptom | Meaning | What to do |
|---|---|---|
| `curl …/healthz` prints `db unavailable` (HTTP 503) | `web` is up but cannot reach Postgres | Run `docker compose ps` and `docker compose logs db`. A `db` that is not healthy usually means a bad volume, so reset with `docker compose down -v` and `make demo` |
| `make demo` says `keygen exited with 1`, and the log says "DB data exists but its secrets are gone" | The `secrets-db` volume was removed while `pgdata` was kept, so the new passwords would not match the existing roles | Run `docker compose down -v`, then `make demo`. The data is synthetic |
| `make demo` says `migrate exited with …` | A migration or bootstrap step failed. `web` never starts, so nothing restarts in a loop | Read `docker compose logs migrate keygen`. Fix the code or reset with `docker compose down -v` |
| `make demo` times out waiting for `web` | `web` started but never became healthy | Read `docker compose logs --tail 50 web`. The entrypoint prints which secret file is missing, if any |
| `docker compose logs migrate` shows `CommandError: data already present; use --reset (demo mode) to reseed` | `seed_demo` was run by hand on a database that already has data. `bootstrap_demo` itself only seeds an empty database | Use `make reseed` (wipes and reseeds), or leave the data as it is |
| `make reseed` fails with `CommandError: --reset is only allowed with CC_DEMO_MODE=true` | The stack runs with `CC_DEMO_MODE=false`, so wiping data is refused on purpose | Set `CC_DEMO_MODE=true` (the default) and run `make demo`, or reset everything with `docker compose down -v` |
| `migrate` exits non-zero right after you pull Phase 2, on a volume created in Phase 1 | Migrations `accounts.0002` and `0003` add required columns. They work only on an empty user table, and they cannot be reversed without losing data | Run `docker compose down -v`, then `make demo`. The data is synthetic |
| Port 8000 is in use | Another process holds the port | Run `WEB_PORT=8010 make demo` |
| CI fails on "Public-safety denylist" for a pull request from a fork | Fork PRs cannot read the `PUBLIC_DENYLIST_REGEX` secret, so the step fails closed on purpose | A maintainer re-runs the change from a branch in this repository |

## Rollback

The demo has no deploy target (plan decision D5). Rolling back means checking out the previous commit and resetting:

```sh
git checkout <previous-sha>
docker compose down -v
make demo
```
