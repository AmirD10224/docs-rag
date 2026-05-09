"""Health and readiness endpoints used by Fly.io's checks.

`/healthz` is a fast liveness probe, does the process reply at all? Fly
sends traffic only to instances whose healthz returns 200, so it must not
do heavy work.

`/readyz` is a readiness probe, are our upstreams reachable and are our
secrets present? It's slower (touches Qdrant + Redis) and is the right
endpoint for an alerting rule.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(tags=["meta"])


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadinessResponse(BaseModel):
    status: str
    version: str
    checks: dict[str, str]
    daily_cost_spent_usd: float
    daily_cost_cap_usd: float


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    from docs_rag import __version__

    return HealthResponse(status="ok", version=__version__)


@router.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    from docs_rag import __version__

    container = getattr(request.app.state, "container", None)
    if container is None:
        return JSONResponse(
            {"status": "starting", "version": __version__, "checks": {}},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    checks: dict[str, str] = {}
    settings = container.settings

    # Secrets present? (Skip when MOCK_PROVIDERS=true, those use stub providers.)
    if not settings.mock_providers:
        for name, secret in (
            ("anthropic_api_key", settings.anthropic_api_key),
            ("cohere_api_key", settings.cohere_api_key),
            ("jina_api_key", settings.jina_api_key),
        ):
            checks[name] = "ok" if secret.get_secret_value() else "missing"

    # Cache reachable?
    try:
        await container.cache.set("readyz_probe", "1", ttl_seconds=10)
        await container.cache.get("readyz_probe")
        checks["cache"] = "ok"
    except Exception as exc:
        checks["cache"] = f"error: {exc.__class__.__name__}"

    spent, cap = await container.cost_guard.snapshot()
    payload = ReadinessResponse(
        status="ok" if all(v == "ok" for v in checks.values()) else "degraded",
        version=__version__,
        checks=checks,
        daily_cost_spent_usd=round(spent, 4),
        daily_cost_cap_usd=cap,
    )
    code = status.HTTP_200_OK if payload.status == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(payload.model_dump(), status_code=code)
