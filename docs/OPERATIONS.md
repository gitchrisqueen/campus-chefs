# Operations runbook

The demo runs locally with Docker Compose. Seeded offerings are timed relative to the first boot, so a volume kept for more than a week runs out of future meals: run `make reseed`. All of its data is synthetic and disposable, and **there are no backups**: the reset for any problem is `docker compose down -v`, then `make demo`.

## Prerequisites

- Docker Engine with Compose v2. Phase 1 was tested on Engine 29.9.3 with Compose v5.7.0 (`docs/architecture.md`).
- `make`, `curl` and `jq`.
- About 3 GB of free disk space. The runtime image is 175 MB; the test image with Chromium is 1.92 GB.
- For `make sast` only: `uv` on the host. For `make screenshots` only: `exiftool` on the host. `make screenshots` and `make docs-check` also pull two pinned tool images, about 130 MB and 590 MB.

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
| Run one test by its plan ID | `make test K="auth_07"`, `make e2e K="e2e_01"` |
| Lint, static checks and the docs link check | `make lint` |
| Check the docs | `make docs-check` checks links, image paths and alt text, then renders every Mermaid diagram in `README.md` and `docs/architecture.md` with a pinned mermaid-cli image. Its last line is `render-mermaid: 2 file(s) rendered` |
| Recapture the README and walkthrough pictures | `make screenshots`, with the demo running. It reseeds, captures `docs/screenshots/after/` and `docs/screenshots/walkthrough/`, rebuilds `hero.gif`, reseeds again and checks every image for metadata. Review the pictures before you commit them: the dates in them move with the day you run it |

## Admin account

No staff account is seeded, and the demo personas have no password, so they cannot log in to the admin.

1. List the campus ids:
   `docker compose exec web python manage.py shell -c "from meals.models import Campus; print(list(Campus.objects.values_list('id', 'name')))"`.
   The ids change after a reseed, except for campuses that a staff account belongs to.
2. Create the account: `docker compose run --rm migrate python manage.py createsuperuser`. It asks for email, first name, last name, a campus id and a password. For a scripted run, add `-e DJANGO_SUPERUSER_PASSWORD=...` and `--noinput --email ... --first_name ... --last_name ... --campus <id>`.
3. Sign in at http://127.0.0.1:8000/admin/.

## Moderation

Only a staff account (see "Admin account") can hide a review, and only through the admin. The same people can un-hide it.

- **Hide:** open `/admin/bookings/review/`, tick the review, choose "Hide selected reviews" and press Go. A hidden review disappears from the cook page and from the average. The action writes an entry in the admin history of each review and shows "Hid N review(s)." The server log gets one line with ids only (`review hidden: review <id> by staff <id>`).
- **Un-hide:** open the review (`/admin/bookings/review/<id>/change/`), clear the "Hidden at" date and time, and save. The booking and the rating are read-only there, so a staff member cannot change what the diner wrote.
- **Not undoable from the app:** account deletion. It anonymizes the user and blanks their free text for good, so the only way back is a database snapshot. The demo has no backups (see the top of this page), so treat a deletion as final.
- **`make e2e` wipes the demo data:** it runs `make reseed` first, which deletes and recreates every synthetic row. Use `NO_RESEED=1 make e2e` to keep the data, and expect a reseed to remove any review you hid by hand.
- **Audit lines:** the app logs booking state changes, kitchen changes (meals and dishes), account deletions and review hides at INFO to stdout, with ids only and never a name, email or free text. Read them with `docker compose logs web`.

## What starts, in order

1. `keygen` (one-shot, no network) generates the secrets on first run and gives each service only its own.
2. `db` (Postgres 18) starts on an internal network with no published port.
3. `migrate` (one-shot) runs `python manage.py bootstrap_demo`. It applies migrations, prepares the cache table, clears expired sessions and, on a fresh database with `CC_DEMO_MODE=true` (the compose default), seeds the synthetic demo data.
4. `web` (gunicorn) starts only after `migrate` has exited 0, and listens on `127.0.0.1:8000`.

## Accounts and demo switches

These are set in `compose.yaml` (`x-app-env`). Override them in `.env` or on the command line, then run `make demo`.

| Variable | Default | Effect |
|---|---|---|
| `CC_DEMO_MODE` | `true` | Shows the demo banner and the "Try as demo diner/cook" buttons. With `false`, `POST /demo/login/<persona>` returns 404 and `make reseed` is refused |
| `CC_REGISTRATION_OPEN` | `true` | With `false`, `/register` returns 404. Use this for any hosted demo |

- **Logged-in pages** (`/me`, account edit, password, delete) send `Cache-Control: private, no-store`.
- **Account deletion** needs the current password. It anonymizes the user (email, name; campus, class year and the 18+ time stay on the row), cancels their active bookings, blanks the terms and notes on all their bookings and the text of their reviews (ratings stay), and clears a cook's bio. Deleting a cook account also cancels their upcoming meals (bookings on them are system-cancelled and bring-list claims released) and retires their dishes, so the cook page disappears (ACCT-03).
- **Failed logins:** see the 429 row below. The cause of a failed login is never logged per user, by design.
- **Parallel stacks** (other worktrees): set `COMPOSE_PROJECT_NAME`, `WEB_PORT` and `CC_IMAGE` so stacks never share containers, ports or images.

## AI menu import (optional)

Off by default. With `CC_AI_ENABLED=false`, `/kitchen/import` returns 404 and the Claude SDK is never loaded. The pasted menu text is sent to the Claude API only when this is on and a cook uses it. Nothing else about the cook is sent.

**Before you turn it on.** Anthropic's commercial terms and data-retention settings have NOT been reviewed for this project. The owner must read and accept them first. Turning the flag on is a decision to disclose pasted text to a third party: Anthropic receives every pasted menu and may keep it for a limited time under its own terms. The site shows that on `/privacy` and on the paste screen, and it tells cooks not to paste names, phone numbers, addresses or health details. It cannot stop a cook who pastes them anyway.

**Turn it on**

1. Put the API key in a file outside the repository, for example `~/.config/campuschefs/anthropic_key`, mode 0400. Never put the key in `.env`, `compose.yaml` or a chat.
2. Make the file readable by the container user (uid 10001). The container reads the file as that user, not as you. A key file that only you can read fails as `PermissionError` (see "If it fails"). On Linux, run `sudo chown 10001 <file>` and keep mode 0400. Otherwise use mode 0444 and keep the file in a directory only you can open.
3. Create `compose.override.yaml` (it is not committed) so the web container can read the file:

   ```yaml
   services:
     web:
       environment:
         ANTHROPIC_API_KEY_FILE: /run/anthropic_key
       volumes:
         - ${HOME}/.config/campuschefs/anthropic_key:/run/anthropic_key:ro
   ```

4. Run `CC_AI_ENABLED=true make demo`. Optional: `CC_AI_MODEL=<model id>` (default `claude-opus-5-5`).
5. Log in as a cook. The kitchen shows "Paste a menu", and `/privacy` gains the lines about the AI service.

**Pre-flight (the owner runs this once, before enabling it for real).** The build never calls the real API, so this is the first live call.

1. With the flag on, log in as a demo cook, open "Paste a menu" and paste two synthetic lines, for example `Lemon pancakes with butter` and `Fruit salad`. Submit.
2. The review page should list both dishes, with nothing saved yet. Leave without saving, or confirm and delete the dishes.
3. `docker compose logs web | grep "menu draft"` should end with a success line like `menu draft: model claude-opus-5-5 request <request id> dishes 2`. A line that starts `menu draft failed` is a failure: look the `error` value up in the table below.

**Cost and limits.** API fees apply only while it is on and a cook submits a menu. One request is at most 4,000 characters in and a short draft out. Each cook may draft 5 menus per 10 minutes and 20 per day (`DRAFT_LIMITS` in `menuparse/views.py`). Only a valid form counts, and it counts before the API call. Over a limit, the cook sees a friendly message and the link to the manual form (HTTP 429), and no API call is made. The counters live in the `cc_ratelimit` cache table. The window starts at a cook's first counted draft, and a restart does not reset it, but `docker compose down -v` does. If the counter table is unavailable, drafting is refused rather than left unlimited. Also set a monthly spend limit in the Anthropic console.

**Turn it off.** Run:

```sh
CC_AI_ENABLED=false make demo
```

This recreates the web container, so a restart is needed and the change is not live until it finishes. Then check both:

```sh
docker compose exec web env | grep CC_AI_ENABLED
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/kitchen/import
```

The first prints `CC_AI_ENABLED=false`. The second prints `404`. The flag check runs before the login check, so with the flag off the page is a 404 for everyone: an anonymous visitor gets 404 (not a redirect to login), and so does a logged-in cook. Use your `WEB_PORT` instead of 8000 if you changed it. "Paste a menu" disappears from the kitchen and the AI lines disappear from `/privacy`. Remove the key file and the override to finish. Rotating or revoking the key is done in the Anthropic console.

**If it fails.** `docker compose logs web | grep "menu draft"` shows the model id, the request id and the error, never the pasted text. A failed draft logs `menu draft failed: model <id> request <id> error <value>`. Find `<value>` in this table. A cook always sees a friendly message and a link to the manual form.

| Logged `error` value | Likely cause | What to do |
|---|---|---|
| `no_api_key` | `ANTHROPIC_API_KEY_FILE` is not set in the web container, or the key file is empty | Check the override file and `docker compose exec web env \| grep ANTHROPIC`. Put the key in the file |
| `PermissionError` | The key file is not readable by uid 10001 | Make the file readable by that user (step 2 of "Turn it on"), then `make demo` |
| `FileNotFoundError` or `IsADirectoryError` | The key file path in the override is wrong, or the host file did not exist when the container started (Docker then mounts an empty directory) | Fix the host path, create the file, then `make demo` |
| `AuthenticationError` | The key is revoked, wrong or expired | Create a new key in the Anthropic console, write it to the key file, run `make demo` |
| `NotFoundError` | The model id does not exist or this key cannot use it | Set `CC_AI_MODEL` to a model id from the Anthropic model list, then `make demo` |
| `RateLimitError` | Anthropic is throttling this key or the account | Wait, or raise the limits in the Anthropic console. Our own per-cook limit is a separate row below |
| `APITimeoutError` | No answer within 20 seconds (the SDK does not retry) | Try again. If it keeps happening, check status.anthropic.com or try a smaller model through `CC_AI_MODEL` |
| `APIConnectionError` | The container cannot reach the API (network, DNS or proxy) | Check the host network and DNS from inside the container |
| `refusal` | The model declined to draft this text | Nothing to fix. The cook adds the dishes by hand |
| `no_parsed_output` | The reply did not parse into a draft (for example it was cut off) | Try again. If it repeats, check `CC_AI_MODEL` and report the request id |
| `ValidationError` | The reply had a value outside the allowed lists or lengths, so nothing was kept | Try again. If it repeats, report the request id |
| `empty_draft` | The reply held no dishes (the cook sees "could not find any dishes") | The pasted text had no dishes. Nothing to fix |
| Any other class name (for example `BadRequestError`, `PermissionDeniedError`, `InternalServerError`, `RuntimeError`) | An API or unexpected error. The class name is the only detail logged | Look the class up in the Anthropic SDK docs. `InternalServerError` is usually Anthropic's side: wait and try again |
| `menu draft blocked: rate_limited limit burst` or `limit daily` | A cook went over 5 drafts in 10 minutes, or 20 in a day. No API call was made | Nothing to fix. To clear counters: `docker compose exec web python manage.py shell -c "from django.core.cache import caches; caches['ratelimit'].clear()"` (this also clears login lockouts) |
| `menu draft blocked: rate_limited limit unavailable` and `rate limiter unavailable; refusing the request` | The `cc_ratelimit` table is missing or the database errored. Drafting is refused until it is back | Run `make demo` (it recreates the table), then check `docker compose logs migrate` |

`too_long` (more than 4,000 characters) is checked by the form first, so a cook sees a validation error and nothing is logged. The service raises it only as a second guard.

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
| Login returns 429 "Too many failed logins for this email" | 5 failed logins for one email within 15 minutes. The lockout also blocks the correct password until the window ends. `docker compose logs web` shows `login locked for key <prefix>` (no email is logged). The counters live in the `cc_ratelimit` cache table | Wait 15 minutes, or clear every counter: `docker compose exec web python manage.py shell -c "from django.core.cache import caches; caches['ratelimit'].clear()"` |
| `docker compose logs web` shows `rate limiter unavailable` | The `cc_ratelimit` table is missing or the database errored. The limiter fails open, so logins keep working but are not counted | Run `make demo` (`bootstrap_demo` recreates the table with `createcachetable`), then check `docker compose logs migrate` |
| Port 8000 is in use | Another process holds the port | Run `WEB_PORT=8010 make demo` |
| `make lint` ends with `check_docs: N failure(s)` | A relative link, image path or heading anchor in `README.md` or `docs/*.md` points at nothing, an image has no alt text, or the container diagram no longer names something in `compose.yaml` | Each line above the summary gives the file, the line and the target. Fix the path, or update the diagram in both `README.md` and `docs/architecture.md` |
| `make docs-check` fails inside `render-mermaid.sh` | A Mermaid diagram does not parse, or Docker could not pull the mermaid-cli image | Read the parse error printed above the failure and fix the diagram. For a pull failure, check the network and run it again |
| `make screenshots` stops with a Playwright timeout | The demo is not running, or its data is not the fresh seed the capture expects | Run `make demo`, then `make screenshots` again. It reseeds first |
| CI fails on "Public-safety denylist" for a pull request from a fork | Fork PRs cannot read the `PUBLIC_DENYLIST_REGEX` secret, so the step fails closed on purpose | A maintainer re-runs the change from a branch in this repository |

## Rollback

The demo has no deploy target (plan decision D5). Rolling back means checking out the previous commit and resetting:

```sh
git checkout <previous-sha>
docker compose down -v
make demo
```
