# Campus Chefs. Recipes run under sh, so they behave the same from zsh and bash.
# Local default: run tools inside the `tests` container. CI overrides: RUN="uv run".
RUN ?= docker compose --profile test run --rm tests
K ?=
export BASE_URL

.PHONY: test e2e lint sast manage deploy-check demo reseed smoke screenshots docs-check

test:
	mkdir -p test-results && chmod 0777 test-results
	$(RUN) pytest -p no:cacheprovider -m "not e2e" $(if $(K),-k "$(K)") $(if $(COV),--cov --cov-fail-under=90)

e2e:
	mkdir -p test-results && chmod 0777 test-results
	$(if $(NO_RESEED),,$(MAKE) reseed &&) $(RUN) pytest -p no:cacheprovider -m e2e $(if $(K),-k "$(K)") --tracing retain-on-failure

lint:
	$(RUN) sh -c 'ruff check . && ruff format --check . && djlint templates --lint && codespell && python scripts/static_checks.py && python scripts/check_docs.py'

# pip-audit needs PyPI/OSV; the tests container has no internet (backend network only), so sast runs on the host.
sast:
	uv run sh -c 'bandit -q -c pyproject.toml -r accounts meals bookings core menuparse config && uv export --locked --no-hashes --format requirements-txt -o /tmp/cc-req.txt && pip-audit --strict -r /tmp/cc-req.txt'

manage:
	$(RUN) python manage.py $(ARGS)

deploy-check:
	$(RUN) env CC_DEMO_MODE=false CC_DEMO_LOCAL_HTTP=false DJANGO_ALLOWED_HOSTS=campuschefs.example python manage.py check --deploy --fail-level WARNING

demo:
	docker compose up -d --build && scripts/wait-healthy.sh web 180

# Wipes and reseeds the synthetic demo data (allowed only with CC_DEMO_MODE=true).
reseed:
	docker compose run --rm migrate python manage.py seed_demo --reset

smoke:
	scripts/smoke.sh

# README and walkthrough pictures (docs/screenshots/after and walkthrough) and the animated hero.
# Needs the running demo. It reseeds before and after, because the walkthrough run books a seat.
screenshots:
	mkdir -p test-results && chmod 0777 test-results
	$(MAKE) reseed
	$(RUN) python scripts/capture_screenshots.py --after
	$(RUN) python scripts/capture_screenshots.py --walkthrough
	scripts/build-hero-gif.sh
	$(MAKE) reseed
	scripts/check-image-metadata.sh docs/screenshots

# Docs gate: links, image paths and alt text, then every Mermaid diagram through the pinned mermaid-cli.
docs-check:
	python3 scripts/check_docs.py
	scripts/render-mermaid.sh
