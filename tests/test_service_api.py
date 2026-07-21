from fastapi.testclient import TestClient

import inspect

from reachy_mini_openclaw.service_api import app, main


def test_service_defaults_to_single_container_port_7860():
    source = inspect.getsource(main)
    assert 'os.getenv("SERVICE_PORT", "7860")' in source
    assert 'os.getenv("SERVICE_PORT", "7862")' not in source


def test_private_endpoints_require_matching_service_key(monkeypatch):
    monkeypatch.setenv("SERVICE_API_KEY", "sentinel-test-key")
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/v1/status").status_code == 401
    assert client.get("/v1/status", headers={"X-Service-Key": "wrong"}).status_code == 401

    response = client.get(
        "/v1/status",
        headers={"X-Service-Key": "sentinel-test-key"},
    )
    assert response.status_code == 200
    assert response.json()["running"] is False

    events = client.get("/v1/events?after=0", headers={"X-Service-Key": "sentinel-test-key"})
    assert events.status_code == 200
    assert events.json() == {"cursor": 0, "items": []}
