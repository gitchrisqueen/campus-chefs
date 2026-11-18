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
