"""FastAPI app factory.

Built as a function (`create_app`) so tests can spin up an isolated
instance with a custom Container (typically with mock providers).
The module-level `app` exists for `uvicorn docs_rag.main:app`.

Security middleware applied at the app level:
  - CORS (browser cross-origin)
  - Per-IP rate limiting via slowapi
  - Bearer auth dependency on mutating endpoints (when AUTH_BEARER_TOKEN set)

The actual SSRF/cost-cap defenses live alongside the routes that need them.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from docs_rag import __version__
from docs_rag.api import citation, evals, health, ingest, query
from docs_rag.config import Settings, get_settings
from docs_rag.deps import Container, build_container
from docs_rag.observability.logging import configure_logging, get_logger


def _build_limiter(settings: Settings) -> Limiter:
    return Limiter(
        key_func=get_remote_address,
        default_limits=[settings.rate_limit_default] if settings.rate_limit_default else [],
        enabled=bool(settings.rate_limit_default),
        headers_enabled=True,
    )


async def _rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    """SlowAPI exception handler. Typed against `Exception` (not the more
    specific `RateLimitExceeded`) so it satisfies Starlette's
    `add_exception_handler` signature without an explicit cast."""
    detail = getattr(exc, "detail", str(exc))
    return JSONResponse(
        {"detail": f"rate limit exceeded: {detail}"},
        status_code=429,
    )


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    log = get_logger(__name__)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = container is None
        ct = container or build_container(settings)
        app.state.container = ct
        log.info(
            "app.startup",
            env=settings.app_env,
            mock_providers=settings.mock_providers,
            version=__version__,
        )
        try:
            yield
        finally:
            if owned:
                await ct.aclose()
            log.info("app.shutdown")

    app = FastAPI(
        title="DocsRAG",
        version=__version__,
        description="Production RAG over custom documents with citation enforcement.",
        lifespan=lifespan,
    )

    limiter = _build_limiter(settings)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    app.include_router(health.router)
    app.include_router(ingest.router)
    app.include_router(query.router)
    app.include_router(citation.router)
    app.include_router(evals.router)

    # Per-route rate limits (slowapi uses route function objects; we hook
    # them after include_router to avoid touching the route modules).
    if settings.rate_limit_query:
        limiter.limit(settings.rate_limit_query)(query.query)
    if settings.rate_limit_ingest:
        limiter.limit(settings.rate_limit_ingest)(ingest.ingest)

    return app


app = create_app()
