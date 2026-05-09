"""Jina v3 embeddings client with true late chunking.

The Jina v3 endpoint supports `late_chunking=true` natively: send the
whole document plus span boundaries, and it returns one embedding per
span computed from token embeddings of the full forward pass. We use
that mode so chunks downstream of section X retain context from
sections before X. this is the spec's late chunking moat.

The query path uses `task=retrieval.query` for asymmetric retrieval.
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from docs_rag.config import Settings
from docs_rag.observability.pricing import jina_cost
from docs_rag.observability.tracing import traced

_log = structlog.get_logger(__name__)
JINA_API_URL = "https://api.jina.ai/v1/embeddings"


class JinaError(RuntimeError):
    """Raised on non-retryable Jina API errors."""


class JinaEmbeddingClient:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._http = http_client or httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        self._owns_http = http_client is None

    @property
    def dimensions(self) -> int:
        return self._settings.embedding_dimensions

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def embed_query(self, text: str) -> list[float]:
        vectors, _ = await self._call(
            inputs=[text],
            task="retrieval.query",
            late_chunking=False,
        )
        return vectors[0]

    async def embed_chunks_late(
        self, full_text: str, chunk_spans: list[tuple[int, int]]
    ) -> tuple[list[list[float]], int]:
        if not chunk_spans:
            return [], 0

        vectors, tokens = await self._call(
            inputs=[full_text],
            task="retrieval.passage",
            late_chunking=True,
            chunk_spans=chunk_spans,
        )
        if len(vectors) != len(chunk_spans):
            raise JinaError(f"jina returned {len(vectors)} vectors for {len(chunk_spans)} spans")
        return vectors, tokens

    async def _call(
        self,
        *,
        inputs: list[str],
        task: str,
        late_chunking: bool,
        chunk_spans: list[tuple[int, int]] | None = None,
    ) -> tuple[list[list[float]], int]:
        payload: dict[str, Any] = {
            "model": self._settings.embedding_model,
            "input": inputs,
            "task": task,
            "dimensions": self._settings.embedding_dimensions,
            "late_chunking": late_chunking,
        }
        if chunk_spans is not None:
            payload["chunk_spans"] = [list(s) for s in chunk_spans]

        headers = {
            "Authorization": f"Bearer {self._settings.jina_api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
            retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
            reraise=True,
        ):
            with attempt:
                response = await self._http.post(JINA_API_URL, json=payload, headers=headers)
                if response.status_code >= 500 or response.status_code == 429:
                    response.raise_for_status()
                if response.status_code >= 400:
                    raise JinaError(f"jina {response.status_code}: {response.text[:300]}")

        body = response.json()
        vectors = [item["embedding"] for item in body["data"]]
        usage = body.get("usage", {})
        tokens = int(usage.get("total_tokens", _approx_tokens("".join(inputs))))

        with traced(
            "embed.jina",
            cost_usd=jina_cost(tokens, self._settings),
            tokens=tokens,
            count=len(vectors),
            late_chunking=late_chunking,
        ):
            pass
        return vectors, tokens


def _approx_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))
