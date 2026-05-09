"""Cohere Rerank 3.5 client.

We use the v2 rerank endpoint with `rerank-v3.5`. The output is sorted
descending by relevance_score; we return original-index tuples so the
caller can re-key into chunk records without us mutating their list.
"""

from __future__ import annotations

import asyncio

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from docs_rag.config import Settings
from docs_rag.observability.pricing import cohere_rerank_cost
from docs_rag.observability.tracing import traced

_log = structlog.get_logger(__name__)
COHERE_RERANK_URL = "https://api.cohere.com/v2/rerank"


class CohereError(RuntimeError):
    pass


class CohereRerankClient:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._http = http_client or httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        self._owns_http = http_client is None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def rerank(self, query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
        if not documents:
            return []
        if top_k <= 0:
            return []

        payload = {
            "model": self._settings.rerank_model,
            "query": query,
            "documents": documents,
            "top_n": min(top_k, len(documents)),
        }
        headers = {
            "Authorization": f"Bearer {self._settings.cohere_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
            retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
            reraise=True,
        ):
            with attempt:
                response = await self._http.post(COHERE_RERANK_URL, json=payload, headers=headers)
                if response.status_code >= 500 or response.status_code == 429:
                    response.raise_for_status()
                if response.status_code >= 400:
                    raise CohereError(f"cohere {response.status_code}: {response.text[:300]}")

        body = response.json()
        results = body.get("results", [])
        with traced(
            "rerank.cohere",
            cost_usd=cohere_rerank_cost(1, self._settings),
            doc_count=len(documents),
            returned=len(results),
        ):
            pass
        return [(int(r["index"]), float(r["relevance_score"])) for r in results]
