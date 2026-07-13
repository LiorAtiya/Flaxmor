"""Liveness and readiness endpoints.

- /health: liveness — the process is up and serving requests.
- /ready:  readiness — the service is actually able to do its job
           (an OpenAI API key is configured).
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Always 200 while the process is alive."""
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> JSONResponse:
    """200 when configured to reach OpenAI; 503 otherwise."""
    settings: Settings = get_settings()
    if not settings.openai_api_key:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "OPENAI_API_KEY is not configured"},
        )
    return JSONResponse(status_code=200, content={"status": "ready"})
