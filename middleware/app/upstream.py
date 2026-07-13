"""Upstream (OpenAI) failure handling: map transport errors to clean,
OpenAI-style error responses so a client never sees a stack trace.
"""

from typing import Any

import httpx
import structlog
from fastapi.responses import JSONResponse

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger()


def openai_error_body(message: str, error_type: str, code: str) -> dict[str, Any]:
    """Build an error body in the exact shape the OpenAI API uses."""
    return {"error": {"message": message, "type": error_type, "param": None, "code": code}}


def map_transport_error(exc: httpx.HTTPError) -> JSONResponse:
    """Translate an httpx transport failure into a clean HTTP error response.

    - Timeout (connect/read/write/pool) -> 504 Gateway Timeout
    - Any other transport error (DNS, refused connection, ...) -> 502 Bad Gateway
    """
    status_code: int
    code: str
    message: str
    if isinstance(exc, httpx.TimeoutException):
        status_code, code, message = 504, "upstream_timeout", "The upstream OpenAI request timed out."
    else:
        status_code, code, message = 502, "upstream_unavailable", "The upstream OpenAI API is unreachable."

    logger.error("upstream_transport_error", error=type(exc).__name__, status=status_code)
    return JSONResponse(status_code=status_code, content=openai_error_body(message, "upstream_error", code))
