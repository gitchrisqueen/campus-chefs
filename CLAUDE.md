# CLAUDE.md: Campus Chefs

## What this project is

Campus Chefs is a 2008 student web app, being rebuilt as a 2026 one. It matches college students who want a home-cooked meal with students who like to cook. The flow has three steps: **Register, Search** (by cook or by ingredient), then **Book and eat**.

The diner **chips in toward the groceries** in one of three ways:
- a per-seat share of the grocery cost;
- an item from the cook's bring list;
- terms the two of them agree on.

This supplements the food budget of a student who likes to cook. It is cost-sharing, not selling meals for profit.

## Current state (2026-11-19)

- Phases 0 to 10a and phase 12 are merged to `main`. Phase 10b (the live legacy harness) was dropped (D3).
- Phase 11 (the README, the screenshots and the docs) is on the branch `phase-11-portfolio`. It merges only after the owner approves the README.
- The AI menu import (phase 12) is off by default and has never called the real API. Never add a test or a CI step that calls it.

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

## Tooling and team (owner, 2026-11-18)

- **graft first.** The code graph is built with `graft build .` into `graft/`, which is git-ignored and local. Use the graft tools (`graft_find_code`, `graft_trace_calls`, `graft_file_api`) or `graft ask "<question>"` before grepping or reading files. Rebuild after big changes.
- **caveman voice.** `AGENTS.md`, `.cursor/`, `.windsurf/`, `.clinerules/`, `.opencode/` and `.github/copilot-instructions.md` hold the always-on caveman rule. Chat stays terse. Code, docs, commits and PR bodies stay in full sentences.
- **A team of agents.**
  - **Builders:** each phase, or each independent slice of one (for example phases 4 and 5), goes to a builder subagent in its own git worktree. Each builder prefixes every `make` and `docker compose` command with its own `COMPOSE_PROJECT_NAME`, `WEB_PORT` and `CC_IMAGE`, so parallel stacks never share containers, ports or images.
  - **Coordinator:** the main session plans, integrates and verifies.
  - **Code review:** every PR gets the `product-code` adversarial review (claims, operator and security personas) before it merges.
  - **UX review:** any PR that changes screens or copy also gets a UX review (the `product-content` personas: recipient, brand editor, accessibility, art director). The review uses real screenshots at phone and desktop width, in light and dark mode.
  - **README review:** the README and hiring-facing docs get the `portfolio` review, then the owner's approval.

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
- **Commands:** `make demo`, `make test`, `make e2e`, `make lint`, `make sast`, `make smoke`, `make reseed`, `make deploy-check` (plan 6.3).
  - `make screenshots` recaptures the README and walkthrough pictures and the hero GIF. It needs the running demo and reseeds it.
  - `make docs-check` checks the docs' links, images and alt text, then renders every Mermaid diagram.

## `legacy/` rules

- **Read-only.**
  - `legacy-support/SHA256SUMS` pins every byte.
  - A CI gate fails PRs that touch `legacy/` without the `legacy-change` label.
- **Never run it.** It has a SQL-injection login bypass. The "before" evidence is static only (phase 10a).
- **Redactions:** the photos are placeholders and nine literals are redacted (`legacy-support/REDACTIONS.md`). Never reintroduce the original values anywhere.
- **No license.** `LICENSE` covers everything except `legacy/`.

## Copy rule (owner, 2026-11-18)

- **No "2008" in the product.** The idea started in 2008, but user-facing pages, templates and UI copy do not mention it. The only exception is a history or about section.
- **Where the 2008 story belongs:** developer and history docs (`docs/before-after.md`, `docs/LEGACY-MAP.md`, the plan, `legacy/`), legacy-regression tests, and the README's before/after section.

## Security rules for new code

- **Database:** ORM or parameterized queries only (CHK-04).
- **Passwords:** hashed with Argon2. Credentials travel only by POST. CSRF is on everywhere.
- **Secrets:** read from `*_FILE` paths that the keygen container generates. Commit only `.env.example`, with no values.
- **Authorization:** a user changes only rows they own. Another user's object returns 404, not 403.
- **Demo framing:** the demo banner, `/safety` and `noindex` stay on.
- **Data:** synthetic only. Fictional campuses ending in "(Demo)", and `.example` emails.
