# Architecture notes

This file records the facts the plan said to confirm during implementation (`docs/MODERNIZATION_PLAN.md`). The full design is in plan sections 2, 5, 6 and 8.

## Phase 1 records (2026-11-18)

### Versions tested

| Component | Version | How it was checked |
|---|---|---|
| Docker Engine | 29.9.3 | `docker version` |
| Docker Compose | v5.7.0 | `docker compose version` |
| Python image | `python:3.14.10-slim@sha256:9aaa4740…802f` | `docker buildx imagetools inspect` |
| uv | 0.13.7 (`ghcr.io/astral-sh/uv@sha256:96f40d39…b490`) | same |
| Postgres | `postgres:18.7-alpine3.24@sha256:b6972e11…f015`; postgres UID 70; `PGDATA=/var/lib/postgresql/18/docker` | `docker run … id postgres` |
| alpine (keygen) | `alpine:3.24@sha256:f59abe65…71bf` | `docker buildx imagetools inspect` |
| Django | 6.1.3 | `uv lock` |
| htmx | 4.0.1 (npm `htmx.org-4.0.1.tgz`, sha512 integrity matches the registry; published 2026-11-01) | npm registry |
| gitleaks | v8.30.1 | GitHub releases |
| Trivy | 0.76.1. Not 0.76.2 (2026-11-05), because it is less than 14 days old | GitHub releases |

The full digests are pinned in `Dockerfile`, `compose.yaml` and `.github/workflows/ci.yml`. CHK-08 enforces the pins.

### Questions phase 1 had to answer

- **Django CSP names:** the setting is `SECURE_CSP` and the middleware is `django.middleware.csp.ContentSecurityPolicyMiddleware`, with constants in `django.utils.csp.CSP`. Both were checked in the installed Django 6.1.3.
- **htmx 4 config keys:**
  - `includeIndicatorCSS: false` stops htmx from injecting its indicator stylesheet. The indicator CSS ships in `static/css/app.css` instead.
  - `<meta name="htmx-config">` accepts JSON when the value starts with `{`.
  - htmx 4 has **no `allowEval` switch.** It compiles JavaScript only for `hx-on` handlers and `js:` expressions, and this app uses neither. Under `script-src 'self'` any such use would fail, and E2E-06 would catch it.
- **`docker compose up --wait` with one-shot services:** it exits 0 when `keygen` and `migrate` have exited 0 and `web` and `db` are healthy (Compose v5.7.0). `make demo` still uses `scripts/wait-healthy.sh`, because that script also fails fast and prints logs when a one-shot service exits non-zero.
- **Image sizes:**
  - `campuschefs:local` (runtime): 173 MB.
  - `campuschefs:dev` (tests, with Chromium): 1.92 GB.

## Phase 1 deviations from the plan

Each item below is a deliberate change to the plan's text. None changes scope.

| Plan said | Built | Why |
|---|---|---|
| `make sast` runs in the `tests` container | `make sast` runs on the host with `uv run` | pip-audit needs PyPI/OSV access, and the `tests` container sits only on the internal `backend` network. CI was already on the host |
| `tests/conftest.py` | `conftest.py` at the repo root | The static-storage fixture must apply to the per-app tests (`core/tests/…`) as well as to `tests/` |
| Send `Cross-Origin-Opener-Policy: same-origin` everywhere | Sent only when `CC_DEMO_LOCAL_HTTP=false` (HTTPS) | Browsers ignore COOP on plain-HTTP origins and log a console error, which would fail E2E-06. It has no effect there anyway |
| OPS-03 POSTs to `/login` and expects 302 | Phase 1 POSTs to `/admin/login/` with wrong credentials and expects 200 (a 403 would mean the CSRF origin check failed) | `/login` arrives in phase 3. Phase 3 switches OPS-03 to `/login` with 302 |
| — | Runtime image: `apt-get upgrade`, and pip removed | Trivy found HIGH CVEs in pip's vendored urllib3 and msgpack and in Debian `zlib1g`. Nothing at runtime needs pip |
| — | The dev image installs `git` and `libatomic1` | SEC-06 needs git. Playwright's bundled Node needs `libatomic1` on slim Debian |
| — | Partial tests with a letter suffix (`LEG-06a`, `SEC-03a`, `OPS-01a`, `E2E-06a`, `AUTH-00a`) | CI enforces 90% coverage from phase 1. These test code that exists now, and the owning phase adds the full test under the plain ID |
| — | pytest-playwright `--output test-results/playwright` | The plugin deletes its output folder at startup, and `test-results` is a bind-mount point inside a read-only `/src` |

## Phase 3 records (2026-11-18)

- **OPS-03** now GETs `/login`, POSTs a real login with the CSRF token on port 8010 and expects 302. The script creates a throwaway account (`ops03@ops-check.example`, random password) through the `web` container, because the seeded personas have unusable passwords.
- **OPS-02** builds the secrets volume name from `${COMPOSE_PROJECT_NAME:-campuschefs}`, so a check run under another project name never removes the default stack's volume.
- **Failed-login limiter** (`core/ratelimit.py`): a failed login is a POST that re-renders the form (200). A successful login (302) clears the counter. Each failure is written with `cache.set(..., 15 min)`, not `cache.incr`, because `BaseCache.incr` re-sets the key with the default 5-minute timeout. The known gaps (not atomic across workers; anyone who knows an email can lock it for 15 minutes) are in the module docstring until `SECURITY.md` lands in phase 11.

## Phase 3 deviations from the plan

| Plan said | Built | Why |
|---|---|---|
| `/safety` arrives in phase 8 | A plain `/safety` page with the five points from plan 5.5, linked from the footer | SEC-03 is in the phase 3 exit and checks that `/safety` stays on when demo mode is off. Phase 8 owns the final copy and design |
| The demo-login route "exists only when `CC_DEMO_MODE=true`" | The route is always in the URLconf, and the view returns 404 (for every method) unless `CC_DEMO_MODE` is true | Same behaviour from outside, and the switch can be tested without reloading the URLconf |
| Login with "email and password" | The form field is named `username` (labelled "Email"), as in Django's `AuthenticationForm` and the admin login | One limiter wraps both `/login` and `admin.site.login` and reads the same field |
| — | Login matches the email case-insensitively (`UserManager.get_by_natural_key` uses `iexact`) | Emails are already unique on `Lower(email)`, so `Ava@…` and `ava@…` are one account |
| Account deletion, the diner path | The diner path, plus releasing any bring-list item that a cancelled booking had claimed | Leaving a claim on a cancelled booking would block that item for other diners. The cook path stays with ACCT-03 (phase 6) |
| — | "Try as demo cook" and "Try as demo diner" buttons on `/` and `/login` | Plan 1.2 demo layer; they make the demo login reachable without curl |
| — | codespell: `brunch` added to the ignore list, and the local `graft/` index skipped | `make lint` already failed on the phase 2 base: codespell reads the meal-type example "brunch" (seed and DATA-03) as a typo. `graft/` is a git-ignored local code index |
| — | `test_leg_02a_…` (letter suffix) | `/me` exists now, so the part of LEG-02 that phase 3 can prove (own profile shown, another user's never) runs now. Phase 6 adds the bookings part under the plain ID |

## Phase 4 records (2026-11-18)

- **Money:** `meals/money.py` holds `format_cents` (`400` → `$4.00`) and `suggested_share_cents` (estimate ÷ (seats + 1), rounded down to $0.25). The `money` template filter wraps `format_cents`. Forms take dollars (`DecimalField`, 2 places) and store integer cents; no model has a float or decimal column (CONTRIB-10).
- **Constraint checks in forms:** a ModelForm skips any model constraint that touches a field outside the form (`cook`, the `*_cents` fields). So `MenuItemForm.clean` checks the duplicate-name and one-specialty rules itself, and `OfferingForm.clean` checks the no-profit rule itself. The DB CHECK and unique constraints still back all three.
- **Help text is rendered unescaped** by Django's `django/forms/field.html` (`help_text|safe`). The one dynamic help text (claimed bring-list items on the offering form) passes the cook's labels through `django.utils.html.escape` first.
- **Seats taken** come from a correlated subquery (`OfferingQuerySet.with_seats_taken`), not a join, so text and filter joins on dishes cannot inflate the sum.

## Phase 4 deviations from the plan

| Plan said | Built | Why |
|---|---|---|
| The allergen lock is a phase 6 deliverable (MENU-05) | The lock is in `MenuItemForm` now, with a supporting test; MENU-05 itself stays in phase 6 | The phase 4 brief asked for it, and it needs only the existing `Booking` model |
| Plan 4.1 lists `/kitchen/setup`, `/kitchen/items/…` and `/kitchen/offerings/…` | Also a `/kitchen` page (bio, meals, menu) and `/kitchen/bio`; `/me` shows a short kitchen panel that links to it | The menu and meal lists are too long for the `/me` panel |
| Offering CRUD | Delete works only while a meal has no bookings; otherwise the cook gets a message | Offering cancellation (with system-cancelled bookings) is a phase 6 deliverable |
| — | A blank grocery share takes the suggested share; the edit form shows "Suggested share: $X.XX" | Plan 3.5 says the form suggests the share; this needs no JavaScript |
| — | An offering's dishes must match its meal type, and a new offering must be in the future | Search filters on the offering's meal type, so a lunch dish on a breakfast meal would mislead diners |
| — | The pickup note is shown to the cook and to confirmed diners now | Plan 3.1 rule; BOOK-14 (phase 6) tests the full matrix |
| — | `templates/403.html` | AZ-01 returns 403 to diners on kitchen routes; the page links to `/kitchen/setup` |
| — | The phase 3 `.summary` list on `/me` stacks below 40rem | Its `max-content` label column made `/me` 430 px wide at a 320 px viewport (found by the phase 4 screenshot check) |
| — | Supporting tests without a plan ID (`meals/tests/test_kitchen.py`, `test_public_pages.py`) | They cover the kitchen and public views for the 90% coverage gate |
