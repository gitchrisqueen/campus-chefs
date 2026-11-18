# CLAUDE.md: Campus Chefs

## What this project is

Campus Chefs is a 2008 student web app, being rebuilt as a 2026 one. It matches college students who want a home-cooked meal with students who like to cook. The flow has three steps: **Register, Search** (by cook or by ingredient), then **Book and eat**.

The diner **chips in toward the groceries** in one of three ways:
- a per-seat share of the grocery cost;
- an item from the cook's bring list;
- terms the two of them agree on.

This supplements the food budget of a student who likes to cook. It is cost-sharing, not selling meals for profit.

## Source of truth

- [docs/MODERNIZATION_PLAN.md](docs/MODERNIZATION_PLAN.md), revision 3, holds:
  - the architecture, data model and test catalogue (test IDs);
  - CI, Docker, the phased roadmap and the decisions.
- The owner's answers are in plan 10.3, "Recorded owner answers":
  - **Answered:** D1 Django, D2 redacted legacy, D3 no live harness, D5 not hosted, D6 public repo, D10 record-only grocery money, D11 MIT license (not for `legacy/`).
  - **Not answered:** D4 and D7-D9 use the recommended option.
- [docs/LEGACY-MAP.md](docs/LEGACY-MAP.md) maps each 2008 file to its 2026 home.

## Stack

- Django 6.1 + htmx 4 (server-rendered, no JS build step)
- PostgreSQL 18, Python 3.14, uv
- Docker Compose: `make demo`
- GitHub Actions with a single `ci` job

Versions were checked on 2026-11-18. Verify them again when a phase starts. Never invent a version number.

## This repo is public

`gitchrisqueen/campus-chefs` is public, so every commit is public permanently. Plan 9.0 has the full rules.

- **Never commit:**
  - personal data or real names;
  - secrets or `.env` files;
  - unredacted 2008 files;
  - local machine paths, hostnames or tracker IDs.
- **Before every push,** run both scans and confirm both pass:
  - `PUBLIC_DENYLIST_REGEX="$(cat ~/.config/campuschefs/denylist)" scripts/denylist.sh`
  - `gitleaks git --redact --no-banner .`
- **README, screenshots and hiring-facing docs** merge only after the owner approves them. Code PRs merge after green CI and review.

## How to work here

- **One phase per branch and PR.**
  - A phase is done only when every command in its **Exit** block exits 0 and CI is green.
  - Record the run URL in the PR.
- **Tests are named by plan ID.** Example: `test_auth_07_sqli_login_bypass_rejected`, so `make test K="auth_07"` selects it.
- **Write the regression tests for the 2008 defects first,** then the code that makes them pass.
- **Simplest working code.** Do not build anything in plan 1.4, "Deliberately not built".
- **Payments are out of scope:**
  - The app records grocery contributions and never handles money (D10).
  - A no-profit CHECK caps shares at the grocery estimate.
  - DATA-02 bans card, payout and handle columns.
- **Commands (from phase 1 on):** `make demo`, `make test`, `make e2e`, `make lint`, `make sast`, `make smoke`, `make reseed`, `make deploy-check` (plan 6.3).

## `legacy/` rules

- **Read-only.**
  - `legacy-support/SHA256SUMS` pins every byte.
  - A CI gate fails PRs that touch `legacy/` without the `legacy-change` label.
- **Never run it.** It has a SQL-injection login bypass. The "before" evidence is static only (phase 10a).
- **Redactions:** the photos are placeholders and nine literals are redacted (`legacy-support/REDACTIONS.md`). Never reintroduce the original values anywhere.
- **No license.** `LICENSE` covers everything except `legacy/`.

## Security rules for new code

- **Database:** ORM or parameterized queries only (CHK-04).
- **Passwords:** hashed with Argon2. Credentials travel only by POST. CSRF is on everywhere.
- **Secrets:** read from `*_FILE` paths that the keygen container generates. Commit only `.env.example`, with no values.
- **Authorization:** a user changes only rows they own. Another user's object returns 404, not 403.
- **Demo framing:** the demo banner, `/safety` and `noindex` stay on.
- **Data:** synthetic only. Fictional campuses ending in "(Demo)", and `.example` emails.
