"""Tests for POST /v1/chat/completions — injection, forwarding, and streaming,
with the OpenAI upstream mocked via respx.
"""

import json
from typing import Any

import httpx
import respx
from fastapi.testclient import TestClient

from app.system_prompt import SYSTEM_PROMPT
from tests.conftest import TEST_API_KEY, TEST_UPSTREAM_URL

CHAT_URL: str = f"{TEST_UPSTREAM_URL}/chat/completions"

NON_STREAM_UPSTREAM_REPLY: dict[str, Any] = {
    "id": "chatcmpl-123",
    "object": "chat.completion",
    "model": "gpt-4o-mini",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
}

SSE_BODY: bytes = (
    b'data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"Hel"}}]}\n\n'
    b'data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"lo"}}]}\n\n'
    b"data: [DONE]\n\n"
)


@respx.mock
def test_system_prompt_injected_into_upstream_request(client: TestClient) -> None:
    route = respx.post(CHAT_URL).mock(return_value=httpx.Response(200, json=NON_STREAM_UPSTREAM_REPLY))

    client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "extract this"}]},
    )

    sent_body: dict[str, Any] = json.loads(route.calls.last.request.content)
    assert sent_body["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert sent_body["messages"][1] == {"role": "user", "content": "extract this"}


@respx.mock
def test_server_api_key_used_client_key_ignored(client: TestClient) -> None:
    """The client's Authorization header must never reach OpenAI."""
    route = respx.post(CHAT_URL).mock(return_value=httpx.Response(200, json=NON_STREAM_UPSTREAM_REPLY))

    client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": []},
        headers={"Authorization": "Bearer client-supplied-key"},
    )

    assert route.calls.last.request.headers["Authorization"] == f"Bearer {TEST_API_KEY}"


@respx.mock
def test_non_stream_response_passed_through(client: TestClient) -> None:
    respx.post(CHAT_URL).mock(return_value=httpx.Response(200, json=NON_STREAM_UPSTREAM_REPLY))

    response = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 200
    assert response.json() == NON_STREAM_UPSTREAM_REPLY


@respx.mock
def test_stream_sse_passed_through_byte_identical(client: TestClient) -> None:
    respx.post(CHAT_URL).mock(
        return_value=httpx.Response(200, content=SSE_BODY, headers={"content-type": "text/event-stream"})
    )

    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}], "stream": True},
    ) as response:
        received: bytes = b"".join(response.iter_bytes())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert received == SSE_BODY


@respx.mock
def test_extra_openai_params_forwarded_untouched(client: TestClient) -> None:
    """Passthrough contract: unknown params (temperature, top_p, ...) survive."""
    route = respx.post(CHAT_URL).mock(return_value=httpx.Response(200, json=NON_STREAM_UPSTREAM_REPLY))

    client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": 111,
        },
    )

    sent_body: dict[str, Any] = json.loads(route.calls.last.request.content)
    assert sent_body["temperature"] == 0.2
    assert sent_body["top_p"] == 0.9
    assert sent_body["max_tokens"] == 111


def test_invalid_json_body_returns_400(client: TestClient) -> None:
    response = client.post(
        "/v1/chat/completions",
        content=b"not json at all",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_json"


def test_messages_not_a_list_returns_400(client: TestClient) -> None:
    """A string `messages` must be rejected, not splatted into characters."""
    response = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": "hello"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_messages"


@respx.mock
def test_upstream_non_json_body_returns_502(client: TestClient) -> None:
    """Upstream returning HTML (broken proxy) must become a clean 502, not a crash."""
    respx.post(CHAT_URL).mock(
        return_value=httpx.Response(200, content=b"<html>gateway error</html>", headers={"content-type": "text/html"})
    )

    response = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_invalid_response"
