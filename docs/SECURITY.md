# Security notes

Campus Chefs is a local portfolio demo with made-up data. This page says what the code defends against, what it does not, and how to report a problem. The test and check IDs are defined in [MODERNIZATION_PLAN.md](MODERNIZATION_PLAN.md), section 7. The trade-offs behind the main choices are in the [README](../README.md#security-and-data-decisions).

## Reporting a problem

Use GitHub's private vulnerability reporting for this repository: <https://github.com/gitchrisqueen/campus-chefs/security/advisories/new>. Do not open a public issue for a security problem.

- Say which page or command is affected and how to reproduce it on a local `make demo`.
- Never include a real person's data. The demo data is synthetic, and reports should be too.
- A finding in `legacy/` is expected. That folder holds the 2008 code as historical reference. It is never run or deployed, and its known defects are listed in [before-after.md](before-after.md).

This is a one-person demo project, so there is no response-time promise.

## What an attacker could want

The demo holds no real personal data and no money. The threats that still matter:

| Threat | Why it matters here |
|---|---|
| The 2008 defects coming back: SQL injection, plain-text passwords, credentials in URLs | They are the reason for the rebuild, and each has a regression test |
| One user reading or changing another user's bookings, menu or account | The app's whole authorization model is "you can change only rows you own" |
| A takeover of the `web` container reaching the database schema or other services' secrets | Compose runs four containers on one host |
| Script or markup injection through names, bios, dish text, terms and reviews | Almost every page shows text typed by another user |
| A secret or a real name being committed | The repository is public and its history is permanent |
| Someone deploying this for real students | Food sharing has legal and allergen risk that the code cannot remove |
| The optional AI menu import, when someone turns it on: pasted text that steers the model, a reply that carries markup or wrong allergens, pasted text leaving the machine, a leaked API key, and a bill run up by repeated requests | It is the only feature that sends data to a third party and the only one that can cost money. It is off by default |

## What is defended

| Area | Control | Proof |
|---|---|---|
| SQL injection | No SQL strings in app code: the ORM binds every value. A static check fails on `.raw(`, `.extra(`, `RawSQL`, `connection.cursor` and `cursor.execute`, and bandit runs alongside it | AUTH-07, SRCH-03, SRCH-09, CHK-04 |
| Output escaping | Template autoescape is always on. A static check bans `\|safe`, `mark_safe` and `{% autoescape off %}`. Values are stored as typed and escaped when shown | REG-09, SRCH-08, LEG-05, CHK-05 |
| Passwords | Argon2id. 12 to 128 characters, checked against common passwords and the user's own details | REG-01, REG-04 |
| Credentials in transit | Login, registration, logout and every state change are POST with a CSRF token. No request URL in a full browser run carries a password | AUTH-03, AUTH-04, AUTH-06, AUTH-09, AUTH-10, REG-08 |
| Sessions | Database-backed, two weeks, `HttpOnly`, `SameSite=Lax`. The session key changes at login. A password change logs out the user's other sessions. Outside local-HTTP mode the cookies are `Secure` and HSTS is on | AUTH-01, AUTH-11, SEC-01, SEC-02 |
| Re-authentication | Changing the email or the password and deleting the account each need the current password | ACCT-02, ACCT-04, AUTH-11 |
| Authorization | Views scope every query to rows the user owns. Another user's object returns 404. On a booking, a participant with the wrong role gets 403 and an impossible transition gets 409 | AZ-01 to AZ-07, BOOK-04, BOOK-09 |
| Mass assignment | Every model form lists its fields. Status, ownership, staff flags and `hidden_at` are never form fields | AZ-08, CHK-07 |
| Browser policy | `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`. Also `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin` and a `Permissions-Policy` that turns off camera, microphone and geolocation | SEC-01, E2E-06 |
| Private pages in caches | Every response to a logged-in user carries `Cache-Control: private, no-store` | SEC-07 |
| Failed logins | 5 failures for one email in 15 minutes lock that email, on `/login` and on the admin login. See the gaps below | AUTH-05 |
| Privacy on public pages | A person appears as a first name and an initial. No email is rendered publicly. Search matches first names only, so it cannot be used to find a surname. A pickup note is shown only to the cook and to confirmed diners | AZ-06, SRCH-10, BOOK-14 |
| Data rules | 19 named CHECK constraints and 5 unique constraints back the forms, including the no-profit rule `share_per_seat_cents * capacity <= grocery_estimate_cents` | DATA-03, CONTRIB-01, CONTRIB-12 |
| Payment data | None exists. The only money columns are `grocery_estimate_cents`, `share_per_seat_cents` and `share_cents`. A test fails if a column name suggests a card, payout, handle or tip | DATA-02 |
| Database role | `web` connects as `campuschefs_app`, which has SELECT, INSERT, UPDATE and DELETE and nothing else. Migrations run in a one-shot container as the owner role. Neither role is a superuser | SEC-04, SEC-05, smoke check 5 |
| Secrets | `keygen` writes 80 random hex characters per secret on first start, into one volume per consumer, as files with mode 0400 owned by the consumer's user id. `web` sees the Django key and the app password. Only `db` sees the superuser password. Nothing secret is committed, and `.env.example` holds no values | SEC-08 (smoke check 4), CHK-06 |
| Containers | `web` and `migrate`: user id 10001, read-only root filesystem, all capabilities dropped, `no-new-privileges`. `db` has no published port and sits on an internal network. `web` is published on `127.0.0.1` only | smoke checks 3 and 4, `compose.yaml` |
| Local-HTTP guard | Plain HTTP is allowed only when every allowed host is a loopback name. Any other host with `CC_DEMO_LOCAL_HTTP=true` stops the app at start | SEC-09 |
| Errors and logs | `DEBUG` is off in the image. Errors show a generic page. Audit lines carry ids only, never a name, an email or free text. A lockout is logged with a hash prefix, not the email | LEG-06, AUTH-05 |
| AI menu import (optional, off by default) | With `CC_AI_ENABLED=false` the route returns 404 and the SDK is never imported. With it on: only the pasted text and a fixed system prompt are sent; the reply must fit a schema built from the app's own allowed values and is validated twice; every value is escaped on the page; nothing is saved until the cook confirms the allergens; each cook gets 5 drafts per 10 minutes and 20 per day, and the counter fails closed. The key is read from a file outside the repository. Logs carry the model id, the request id and the error class, never the pasted text | AI-01 to AI-07, run with a test double in place of the API client |
| Supply chain | `uv.lock` is committed and installed with `--locked`. Actions are pinned by commit SHA and images by digest. CI runs pip-audit, bandit and a Trivy scan of the built image. Dependabot watches GitHub Actions, Docker, Compose and Python packages | CHK-08, `.github/workflows/ci.yml` |
| The public repository | gitleaks scans the full history in CI. A denylist scan checks the tree, file names, history and commit messages, and prints only locations. GitHub secret scanning with push protection is on. `legacy/` is pinned by checksum and guarded by a CI gate | SEC-06, `legacy-support/SHA256SUMS` |

## What is not defended

These are known gaps. Each is accepted for a local demo and would have to be closed before real use.

### The failed-login limiter

The limiter is `core/ratelimit.py`. It counts failed logins per email in a database cache table.

- **It can be used to lock someone out.** Anyone who knows an email address can send five wrong passwords and block that account for 15 minutes, including for its owner with the right password. The limit is per email and not per IP on purpose: behind Docker's port publishing every client can arrive from one gateway address, so a per-IP limit would lock out everyone together. It never reads `X-Forwarded-For`.
- **The count is not atomic.** Each attempt reads the counter and then writes it. With three gunicorn workers, attempts that arrive at the same moment can each read the same number, so an attacker can get a few more than five tries per window.
- **It fails open.** If the cache table is missing or the database errors, logins keep working and are not counted. The log says `rate limiter unavailable`.
- **Registration, search and booking have no rate limit.** Failed logins are limited here. The optional menu import has its own per-cook limit, described below.

### Accounts

- **No email verification.** There is no mail transport, so anyone can register an address they do not own.
- **Registration reveals whether an email has an account.** A second registration with the same email says "This email is already registered" (REG-03). Without email, the usual answer of "check your inbox" is not possible. Login does not have this problem: a wrong password, an unknown email and a deleted account all get the same message (AUTH-02).
- **No password reset.** A forgotten password cannot be recovered through the app.
- **No two-factor authentication.**

### Trust between students

- **Reviews can be gamed.** A cook can register a second account, book their own meal, complete it and review it.
- **Allergen and dietary labels are whatever the cook typed.** The app makes the cook confirm each list, locks it while a booking is active (MENU-05) and makes the diner tick that they read it (BOOK-02). None of that checks the food.
- **The no-profit rule trusts the cook's grocery estimate.** There are no receipts.
- **"Received" is the cook's word.** The app records that the cook marked a share received. It has no proof of payment and no dispute process.

### The AI menu import

The import is off by default (`CC_AI_ENABLED=false`). These gaps apply only when someone turns it on. [OPERATIONS.md](OPERATIONS.md#ai-menu-import-optional) has the steps and the checks to run first.

- **It has never run against the real API.** No test makes a network call: a test double stands in for the API client. The default model id comes from the API documentation and was not checked with a live call. The first real request is the pre-flight in the runbook.
- **Prompt injection is contained, not prevented.** A pasted menu can hold text that tries to give the model instructions. The system prompt tells the model to treat the text as data, but that is not a guarantee. What limits the damage:
  - The reply must fit the schema. One value outside it rejects the whole draft (AI-03).
  - The draft is shown in an editable form with every value escaped, and nothing is saved until the cook ticks the allergen confirmation (AI-02, AI-05).
  - The model has no tools and no access to the database.

  So the worst outcome is a wrong draft, for example a missing allergen. A cook who confirms a draft without reading it saves that mistake, as a cook who mistypes a dish by hand does.
- **Pasted text goes to a third party.** Anthropic receives every pasted menu and may keep it for a limited time under its own terms. Those terms and the retention settings have not been reviewed for this project. The paste screen and `/privacy` say what is sent and tell the cook not to paste names, phone numbers, addresses or health details (AI-07). Nothing stops a cook who pastes them anyway. Deleting an account does not remove text already sent.
- **The API key is a file that the `web` container can read.** It is mounted from the host by a local override file that is not committed. It is not one of the secrets that `keygen` generates, and it is never a Django setting or a value in `compose.yaml`. A takeover of the `web` process can read it. Rotating or revoking it is done in the provider's console.
- **The cost limit is per cook account, and there is no site-wide cap.** With registration open, someone can create several cook accounts and get 20 drafts a day on each. The count is not atomic across the three gunicorn workers, so requests that arrive at the same moment can slip a few past a limit. Set a monthly spend limit in the provider's console, as the runbook says, and set `CC_REGISTRATION_OPEN=false` on anything reachable from outside your machine.

### Operations

- **No backups.** The data is synthetic and the reset is `docker compose down -v`.
- **No HTTPS in the demo.** It listens on `127.0.0.1` over plain HTTP. The HTTPS settings exist and pass `manage.py check --deploy` (SEC-02), but no deployment was built or tested.
- **No monitoring or alerting.** Logs go to the container's standard output.
- **One host.** A compromise of the Docker host or of the `db` container bypasses every control above.
- **The `tests` container can read both the owner and the app database passwords.** It needs them to prove what the app role cannot do. It starts only with `--profile test`.

## The demo framing is a control

The banner, the `/safety` and `/privacy` pages, the `noindex` tag and `robots.txt` exist so that nobody mistakes this for a service. `/safety`, `/privacy`, `noindex` and `robots.txt` stay on when `CC_DEMO_MODE` is off (SEC-03). Set `CC_REGISTRATION_OPEN=false` for anything reachable from outside your machine (REG-11), and do not deploy this with public sign-ups.
