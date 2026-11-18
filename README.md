# Campus Chefs

> Match students who want a good home-cooked meal with students who know how to cook.

Campus Chefs started in 2008 as a student web project. This repository holds that original code and a plan to rebuild it as a 2026 web app with the same idea. The rebuild will be secure, accessible, tested and Docker-deployable.

**Status:** work in progress. Phase 1 of [the plan](docs/MODERNIZATION_PLAN.md) is built: the Django skeleton, the one-command Docker demo and CI. The app features arrive phase by phase. The repository is public from its first commit, so the whole 2008-to-2026 history can be followed.

---

## The idea

The 2008 landing page says:

> "The purpose of this site is to match students looking for a good home cooked meal, with students who know how to cook. This site was built for any college student who would rather sit back and watch someone else cook for them, then [sic] to actually do it themselves."

It worked in three steps:

1. **Register.** Sign up as a **Cook** or a **Customer**, and give your campus, class year and transportation.
2. **Search.** Find meals by student or by ingredient.
3. **Eat!** Book the meal you want and enjoy it.

The diner chips in toward the groceries, either with a share of the grocery cost or by bringing ingredients. This supplements the food budget of a student who likes to cook. The cook gets help with the grocery bill, not a profit. The 2008 code never got as far as building this part.

A cook's profile was to show:
- a breakfast, lunch and dinner menu, split into mains and sides;
- specialties;
- a rating;
- comments split into "the good" and "the bad".

## What the 2008 code does today

| Feature | 2008 state |
|---|---|
| Landing page with the 1-2-3 steps | Built |
| Registration | Form built. It submits by GET, saves the password in plain text and does no validation. It also swaps the `campus` and `profileType` values on insert |
| Login | Built, but it compares the email against the `first_name` column, never starts a session, and is open to SQL injection |
| Cook profile page | Layout built. It always shows user `1`, and the menu and specialties are hardcoded HTML |
| Customer profile page | Empty |
| Search | Text box only; it leads to an "Under Construction" page |
| Booking | Not built |
| Grocery cost-sharing | Not built |
| Comments and ratings | Not built (an empty placeholder) |
| About, Contact, FAQ, How it works, Take the tour | "Under Construction" |
| Tests | Two echo scripts with no assertions |

It no longer runs on any current PHP release. It uses the `mysql_*` extension, which PHP 7.0 removed in 2015. There is also no database schema file. The table layout can only be inferred from the queries in `legacy/src/sqlQueries.php`.

### TODOs left in the code

- `legacy/src/cook_main.php:7`: `//HACK! fix this`, where the user id is hardcoded instead of read from the session.
- `legacy/src/registration_form.php:57,62,67`: transportation and profile type should be radio buttons, and campus a drop-down.
- `legacy/src/cook_profile.php`, `legacy/src/customer_profile.php`, `legacy/src/menu.php`: the method-test sections are marked "delete later".

[Plan section 12](docs/MODERNIZATION_PLAN.md#12-original-code-audit) has the full audit, by file and line.

## The 2026 plan, in short

| | 2008 | Planned for 2026 |
|---|---|---|
| Stack | PHP 5, `mysql_*`, MySQL | Django 6.1, htmx 4, PostgreSQL 18, Python 3.14 |
| Auth | Plain-text passwords sent over GET, no session | Hashed passwords, POST plus CSRF, sessions, rate-limited login |
| Data access | String-concatenated SQL | ORM only; a static check bans raw SQL |
| Features | Register and a static cook page | Register, cook kitchen (menus, allergens, meal offerings), search, bookings with a state machine, grocery cost-sharing (a per-seat share or a bring-list item, capped at the grocery cost), reviews |
| Design | Fixed 1024px layout, corner-image hacks | Responsive, WCAG 2.2 AA, dark mode, tokens taken from the original red `#A40408` brand |
| Tests | Echo scripts | About 110 named tests: unit and integration against real Postgres, Playwright end-to-end, axe accessibility, and one regression test per 2008 defect |
| Deploy | Copy files into a local Apache | `make demo` (Docker Compose, generated secrets, synthetic seed data, healthchecks) |
| CI | None | One GitHub Actions job: lint, SAST, secret and dependency scans, tests, image build and a compose smoke test |

**Demo only.** Students negotiate their own terms: a suggested share, an item from the cook's bring list, or their own offer. The app records what was agreed and never handles money transactions. The cook marks the contribution received. It carries allergen acknowledgements, safety and privacy pages and a demo banner. All seed data is synthetic. It is meant to show how a 2008 student app becomes a 2026 production-quality one. It is not a live food marketplace.

## Repository layout (today)

```
compose.yaml, Dockerfile, Makefile   the one-command demo and the dev commands
docker/          keygen.sh (secrets), entrypoint.sh, postgres-init/01-roles.sh (DB roles)
config/          Django settings and URLs
core/            health check, home page, security middleware, management commands
accounts/        the email-login user model
meals/, bookings/  the domain apps (filled in by phases 2 to 7)
templates/, static/  HTML templates, CSS, vendored htmx 4.0.1
tests/           end-to-end browser tests (Playwright)
scripts/         denylist.sh, check-image-metadata.sh, static_checks.py, smoke.sh, ops-checks.sh, wait-healthy.sh
.github/         workflows/ci.yml (one CI job), dependabot.yml
docs/            MODERNIZATION_PLAN.md, LEGACY-MAP.md, architecture.md, OPERATIONS.md
legacy/          the 2008 code, read-only and redacted; no license granted (see legacy/README.md)
legacy-support/  SHA256SUMS for legacy/, REDACTIONS.md, placeholder images
```

## Running it

You need Docker with Compose v2, `make`, `curl` and `jq`.

```sh
make demo                               # build and start; waits until healthy
curl http://127.0.0.1:8000/healthz      # prints: ok
docker compose logs -f web              # follow the app logs
docker compose down                     # stop, keeping data
docker compose down -v                  # reset: wipes the synthetic data and the generated secrets
make test                               # unit and integration tests
```

The data is synthetic and disposable, so there are no backups. [docs/OPERATIONS.md](docs/OPERATIONS.md) covers what to do when something breaks.

**Do not deploy the 2008 code in `legacy/`.** Its login can be bypassed with SQL injection.

**Contributing:** CI's public-safety denylist step fails closed on pull requests from forks, because forks cannot read the secret it needs. A maintainer re-runs such changes from a branch.

## License

[MIT](LICENSE) for everything except `legacy/`, which is kept for historical reference only, with no license granted.
