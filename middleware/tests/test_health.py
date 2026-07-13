"""Tests for the liveness (/health) and readiness (/ready) endpoints."""

from fastapi.testclient import TestClient


def test_health_always_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_api_key_configured(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_not_ready_without_api_key(client_without_key: TestClient) -> None:
    response = client_without_key.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
