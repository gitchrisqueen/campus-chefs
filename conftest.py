import os

import pytest


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
