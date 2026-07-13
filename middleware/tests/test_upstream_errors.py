"""Tests for upstream OpenAI failure handling — clean errors, no crashes."""

from typing import Any

import httpx
import respx
from fastapi.testclient import TestClient

from tests.conftest import TEST_UPSTREAM_URL

CHAT_URL: str = f"{TEST_UPSTREAM_URL}/chat/completions"

REQUEST_BODY: dict[str, Any] = {
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "hi"}],
}

OPENAI_429_BODY: dict[str, Any] = {
    "error": {"message": "Rate limit reached", "type": "requests", "param": None, "code": "rate_limit_exceeded"}
}

OPENAI_500_BODY: dict[str, Any] = {
    "error": {"message": "The server had an error", "type": "server_error", "param": None, "code": None}
}


@respx.mock
def test_upstream_429_passed_through(client: TestClient) -> None:
    respx.post(CHAT_URL).mock(return_value=httpx.Response(429, json=OPENAI_429_BODY))

    response = client.post("/v1/chat/completions", json=REQUEST_BODY)

    assert response.status_code == 429
    assert response.json() == OPENAI_429_BODY


@respx.mock
def test_upstream_500_passed_through(client: TestClient) -> None:
    respx.post(CHAT_URL).mock(return_value=httpx.Response(500, json=OPENAI_500_BODY))

    response = client.post("/v1/chat/completions", json=REQUEST_BODY)

    assert response.status_code == 500
    assert response.json() == OPENAI_500_BODY


@respx.mock
def test_upstream_error_on_stream_request_returns_clean_json(client: TestClient) -> None:
    """Even when the client asked for a stream, an upstream 401 must come back
    as a clean JSON error (there is no SSE to stream)."""
    respx.post(CHAT_URL).mock(
        return_value=httpx.Response(401, json={"error": {"message": "Invalid API key", "type": "invalid_request_error", "param": None, "code": "invalid_api_key"}})
    )

    response = client.post("/v1/chat/completions", json={**REQUEST_BODY, "stream": True})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


@respx.mock
def test_upstream_timeout_returns_504(client: TestClient) -> None:
    respx.post(CHAT_URL).mock(side_effect=httpx.ReadTimeout("upstream timed out"))

    response = client.post("/v1/chat/completions", json=REQUEST_BODY)

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "upstream_timeout"


@respx.mock
def test_upstream_unreachable_returns_502(client: TestClient) -> None:
    respx.post(CHAT_URL).mock(side_effect=httpx.ConnectError("connection refused"))

    response = client.post("/v1/chat/completions", json=REQUEST_BODY)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_unavailable"


@respx.mock
def test_error_body_always_openai_shaped(client: TestClient) -> None:
    """Open WebUI knows how to render this shape — verify all keys exist."""
    respx.post(CHAT_URL).mock(side_effect=httpx.ConnectError("boom"))

    body: dict[str, Any] = client.post("/v1/chat/completions", json=REQUEST_BODY).json()

    assert set(body["error"].keys()) == {"message", "type", "param", "code"}
