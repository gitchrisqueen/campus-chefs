import pytest


@pytest.mark.django_db
def test_health_01_healthz_ok_without_version_data(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    assert response.content == b"ok"
    assert "no-cache" in response["Cache-Control"]
