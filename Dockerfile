# syntax=docker/dockerfile:1
# Digests resolved 2026-11-18 with `docker buildx imagetools inspect`.
ARG PYTHON_IMAGE=python:3.14.10-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f

FROM ${PYTHON_IMAGE} AS base
COPY --from=ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never UV_PYTHON=/usr/local/bin/python3 \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DJANGO_SETTINGS_MODULE=config.settings
WORKDIR /src
COPY pyproject.toml uv.lock ./

FROM base AS build
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY manage.py ./
COPY config/ config/
COPY core/ core/
COPY accounts/ accounts/
COPY meals/ meals/
COPY bookings/ bookings/
COPY templates/ templates/
COPY static/ static/
COPY docker/entrypoint.sh docker/entrypoint.sh
# Throwaway key scoped to this RUN only; collectstatic opens no DB connection.
RUN DJANGO_SECRET_KEY="$(od -An -tx1 -N40 /dev/urandom | tr -d ' \n')" \
    /opt/venv/bin/python manage.py collectstatic --noinput

FROM ${PYTHON_IMAGE} AS runtime
# Debian security updates (Trivy gate), and no pip at runtime: its vendored libraries carry CVEs
# and nothing installs packages after the build.
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && rm -rf /usr/local/lib/python3.14/site-packages/pip /usr/local/lib/python3.14/site-packages/pip-*.dist-info \
           /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.14 \
 && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /opt/venv /opt/venv
COPY --from=build /src /app
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 DJANGO_SETTINGS_MODULE=config.settings
# Fails the build if the venv interpreter link is broken.
RUN python -c "import django, psycopg, argon2, gunicorn"
WORKDIR /app
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD ["python","-c","import sys,urllib.request as u; sys.exit(0 if u.urlopen('http://127.0.0.1:8000/healthz',timeout=2).status==200 else 1)"]
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn","config.wsgi:application","--bind","0.0.0.0:8000","--workers","3","--timeout","30","--graceful-timeout","20","--access-logfile","-"]

FROM base AS dev
ENV PATH=/opt/venv/bin:$PATH PLAYWRIGHT_BROWSERS_PATH=/ms-playwright COVERAGE_FILE=/tmp/.coverage \
    RUFF_NO_CACHE=true UV_CACHE_DIR=/tmp/uv-cache HOME=/tmp
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-install-project
RUN apt-get update \
 && apt-get install -y --no-install-recommends git libatomic1 \
 && playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --uid 10001 --no-create-home app
USER 10001
# The source is bind-mounted read-only at /src by compose; pytest runs with -p no:cacheprovider.
