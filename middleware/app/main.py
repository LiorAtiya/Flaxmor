"""FastAPI app factory: logging, shared HTTP client lifecycle, request context, routers."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import structlog
from fastapi import FastAPI, Request, Response

from app.config import Settings, get_settings
from app.logging_config import configure_logging
from app.routes import chat, health, models

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create one shared httpx.AsyncClient for the whole process (connection pooling)."""
    settings: Settings = get_settings()
    configure_logging(settings.log_level)

    timeout: httpx.Timeout = httpx.Timeout(
        connect=settings.connect_timeout_seconds,
        read=settings.read_timeout_seconds,
        write=settings.connect_timeout_seconds,
        pool=settings.connect_timeout_seconds,
    )
    app.state.http_client = httpx.AsyncClient(timeout=timeout)
    logger.info(
        "middleware_started",
        openai_base_url=settings.openai_base_url,
        served_models=settings.served_models,
    )
    yield
    await app.state.http_client.aclose()
    logger.info("middleware_stopped")


def create_app() -> FastAPI:
    """Build the FastAPI application with all routes and middleware wired."""
    app: FastAPI = FastAPI(title="OpenAI Injection Middleware", lifespan=lifespan)

    @app.middleware("http")
    async def bind_request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Bind a request_id (+ path/method) so every log line of a request carries it."""
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=str(uuid4()),
            method=request.method,
            path=request.url.path,
        )
        return await call_next(request)

    app.include_router(health.router)
    app.include_router(models.router)
    app.include_router(chat.router)
    return app


app: FastAPI = create_app()
