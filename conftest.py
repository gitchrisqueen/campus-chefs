import os

import pytest
from django.core.management import call_command


@pytest.fixture(autouse=True)
def _plain_static_storage(settings):
    """Unit tests run without collectstatic; the manifest storage would raise."""
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture(scope="session")
def base_url():
    """E2E target: BASE_URL (http://web:8000 in the tests container, 127.0.0.1:8000 in CI)."""
    return os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """The failed-login limiter (core/ratelimit.py) needs its cache table in the test DB."""
    with django_db_blocker.unblock():
        call_command("createcachetable", verbosity=0)
