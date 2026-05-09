"""POST /query, hybrid retrieval + cited synthesis.

Pipeline:
  1. Cache lookup (key = sha256(NFKC-normalized question + sorted(document_ids)
     + top_k + PROMPT_VERSION + synthesis_model)).
  2. Embed query → dense + BM25 (full-corpus scroll) → RRF → rerank.
  3. Synthesize with citation enforcement.
  4. Cache the JSON response (TTL = settings.query_cache_ttl_seconds).

Cache hits short-circuit at step 1 and return immediately with
`trace.cache_hit=true`. The cache key includes PROMPT_VERSION and the
synthesis model name so a prompt edit or model bump invalidates stale
answers automatically.
"""

from __future__ import annotations

import json
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from docs_rag.deps import Container
from docs_rag.observability.cache import stable_key
from docs_rag.observability.cost_guard import CostCapExceeded
from docs_rag.observability.security import auth_required
from docs_rag.observability.tracing import request_scope
from docs_rag.synthesis.prompts import PROMPT_VERSION
from docs_rag.synthesis.schema import QueryRequest, QueryResponse, QueryTrace

router = APIRouter(prefix="/query", tags=["query"])


def _make_dependency(request: Request) -> object:
    container = cast(Container, request.app.state.container)
    return auth_required(container.settings)


@router.post("", response_model=QueryResponse)
async def query(
    payload: QueryRequest,
    request: Request,
    _auth: Annotated[None, Depends(_make_dependency)] = None,
) -> QueryResponse:
    container = cast(Container, request.app.state.container)
    settings = container.settings

    cache_key = "q:" + stable_key(
        payload.question,
        sorted(payload.document_ids or []),
        payload.top_k,
        PROMPT_VERSION,
        settings.synthesis_model,
    )
    cached_raw = await container.cache.get(cache_key)
    if cached_raw is not None:
        cached = QueryResponse.model_validate(json.loads(cached_raw))
        return cached.model_copy(
            update={
                "trace": QueryTrace(
                    retrieval_ms=cached.trace.retrieval_ms,
                    rerank_ms=cached.trace.rerank_ms,
                    synthesis_ms=cached.trace.synthesis_ms,
                    total_ms=cached.trace.total_ms,
                    cost_usd=0.0,
                    cache_hit=True,
                )
            }
        )

    with request_scope() as _trace:
        try:
            retrieval = await container.retriever.retrieve(
                payload.question,
                document_ids=payload.document_ids,
                top_k=payload.top_k,
            )
        except CostCapExceeded as exc:
            raise HTTPException(429, str(exc)) from exc
        if not retrieval.chunks and payload.document_ids is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="no documents indexed; ingest one first",
            )

        try:
            response = await container.synthesizer.answer(
                question=payload.question,
                ranked_chunks=retrieval.chunks,
                retrieval_ms=retrieval.retrieval_ms,
                rerank_ms=retrieval.rerank_ms,
                retrieval_precision=retrieval.retrieval_precision,
                cache_hit=False,
            )
        except CostCapExceeded as exc:
            raise HTTPException(429, str(exc)) from exc

        # Record cost against the daily cap (best-effort; trace.cost_usd
        # is the per-request total).
        try:
            await container.cost_guard.check_and_record(response.trace.cost_usd)
        except CostCapExceeded as exc:
            raise HTTPException(429, str(exc)) from exc

    await container.cache.set(
        cache_key,
        response.model_dump_json(),
        ttl_seconds=settings.query_cache_ttl_seconds,
    )
    return response
