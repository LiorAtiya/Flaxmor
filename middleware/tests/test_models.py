"""Tests for GET /v1/models — the curated static list."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def test_models_returns_openai_list_shape(client: TestClient) -> None:
    response = client.get("/v1/models")

    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["object"] == "list"
    assert isinstance(body["data"], list)
    assert len(body["data"]) > 0


def test_models_contains_curated_ids(client: TestClient) -> None:
    body: dict[str, Any] = client.get("/v1/models").json()
    model_ids: list[str] = [model["id"] for model in body["data"]]

    assert model_ids == ["gpt-4o-mini", "gpt-4o"]


def test_each_model_has_required_openai_fields(client: TestClient) -> None:
    body: dict[str, Any] = client.get("/v1/models").json()

    for model in body["data"]:
        assert model["object"] == "model"
        assert isinstance(model["id"], str)
        assert isinstance(model["created"], int)
        assert isinstance(model["owned_by"], str)


def test_served_models_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """SERVED_MODELS from the environment must be reflected in the endpoint."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("SERVED_MODELS", '["my-custom-model"]')
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as test_client:
            body: dict[str, Any] = test_client.get("/v1/models").json()
        assert [model["id"] for model in body["data"]] == ["my-custom-model"]
    finally:
        get_settings.cache_clear()
