"""GET /v1/models — the curated model list Open WebUI shows in its dropdown.

Static by design (decision log): full control over what users see, no startup
dependency on OpenAI, trivial to unit-test.
"""

from typing import Any

from fastapi import APIRouter

from app.config import Settings, get_settings

router = APIRouter()

_MODEL_CREATED_TIMESTAMP: int = 1_700_000_000  # static placeholder; OpenAI uses unix epoch


@router.get("/v1/models")
async def list_models() -> dict[str, Any]:
    """Return the served models in the OpenAI list format."""
    settings: Settings = get_settings()
    data: list[dict[str, Any]] = [
        {
            "id": model_id,
            "object": "model",
            "created": _MODEL_CREATED_TIMESTAMP,
            "owned_by": "middleware",
        }
        for model_id in settings.served_models
    ]
    return {"object": "list", "data": data}
