"""POST /v1/chat/completions — the heart of the middleware.

Flow: receive request -> prepend system prompt -> forward to OpenAI -> return
the response (streaming SSE passthrough or plain JSON) unchanged.

Passthrough philosophy: the body is parsed minimally (we only need `messages`
and `stream`); everything else is forwarded as-is so any OpenAI-compatible
parameter keeps working.
"""

import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from app.config import Settings, get_settings
from app.injection import Message, prepend_system_prompt
from app.system_prompt import SYSTEM_PROMPT
from app.upstream import map_transport_error, openai_error_body

router = APIRouter()

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger()


def _passthrough_json_response(upstream_response: httpx.Response) -> JSONResponse:
    """Pass the upstream JSON body through with its original status.

    If the upstream body is not valid JSON (broken proxy, HTML error page),
    return a clean 502 instead of raising — a client must never see a stack trace.
    """
    try:
        content: Any = upstream_response.json()
    except ValueError:
        logger.error("upstream_invalid_json", status=upstream_response.status_code)
        return JSONResponse(
            status_code=502,
            content=openai_error_body(
                "The upstream OpenAI API returned a non-JSON response.",
                "upstream_error",
                "upstream_invalid_response",
            ),
        )
    return JSONResponse(status_code=upstream_response.status_code, content=content)


@router.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    """Intercept a chat completion request, inject the system prompt, forward to OpenAI."""
    settings: Settings = get_settings()
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        body: dict[str, Any] = await request.json()
    except ValueError:
        return JSONResponse(
            status_code=400,
            content=openai_error_body("Request body is not valid JSON.", "invalid_request_error", "invalid_json"),
        )

    messages: list[Message] = body.get("messages", [])
    if not isinstance(messages, list):
        return JSONResponse(
            status_code=400,
            content=openai_error_body("`messages` must be an array.", "invalid_request_error", "invalid_messages"),
        )

    is_stream: bool = bool(body.get("stream", False))
    logger.info(
        "request_received",
        model=body.get("model"),
        stream=is_stream,
        message_count=len(messages),
    )

    body["messages"] = prepend_system_prompt(messages, SYSTEM_PROMPT)
    logger.info("prompt_injected", message_count=len(body["messages"]))

    # Client Authorization header is intentionally NOT forwarded — the middleware
    # always authenticates with its own server-side key.
    upstream_request: httpx.Request = client.build_request(
        "POST",
        f"{settings.openai_base_url}/chat/completions",
        json=body,
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
    )

    started_at: float = time.perf_counter()
    logger.info("upstream_request_sent", stream=is_stream)
    try:
        upstream_response: httpx.Response = await client.send(upstream_request, stream=is_stream)
    except httpx.HTTPError as exc:
        return map_transport_error(exc)

    latency_ms: int = int((time.perf_counter() - started_at) * 1000)
    logger.info("upstream_response", status=upstream_response.status_code, latency_ms=latency_ms)

    if not is_stream:
        logger.info("request_completed", status=upstream_response.status_code)
        return _passthrough_json_response(upstream_response)

    if upstream_response.status_code != 200:
        # Upstream refused (bad key, 429, 5xx, ...) — read the small error body
        # and pass it through with the original status. No SSE to stream.
        await upstream_response.aread()
        logger.warning("request_failed", status=upstream_response.status_code)
        return _passthrough_json_response(upstream_response)

    async def stream_body() -> AsyncIterator[bytes]:
        """Re-emit upstream SSE bytes as-is, logging completion/interruption."""
        try:
            async for chunk in upstream_response.aiter_raw():
                yield chunk
            logger.info(
                "request_completed",
                status=upstream_response.status_code,
                total_ms=int((time.perf_counter() - started_at) * 1000),
            )
        except httpx.HTTPError as exc:
            logger.error("stream_interrupted", error=type(exc).__name__)

    return StreamingResponse(
        stream_body(),
        status_code=upstream_response.status_code,
        media_type="text/event-stream",
        background=BackgroundTask(upstream_response.aclose),
    )
