"""Synthesis orchestrator.

Public API: `Synthesizer.answer(question, ranked_chunks)` returns a
`QueryResponse` ready for HTTP serialization.

Flow:
  1. Render synthesis prompt with the reranked chunks.
  2. Call Claude → parse JSON → `enforce()`.
  3. On CitationViolation, render repair prompt → one retry → enforce.
  4. On second failure, surface a refused response (refused=true) so
     the frontend can render an honest "I can't ground this" state.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass

import structlog

from docs_rag.config import Settings
from docs_rag.observability.tracing import current_trace
from docs_rag.providers.base import AnthropicError, SynthesisProvider
from docs_rag.retrieval.hybrid import RankedChunk
from docs_rag.synthesis.citation_enforcer import (
    CitationViolation,
    EnforcementResult,
    enforce,
)
from docs_rag.synthesis.prompts import (
    PROMPT_VERSION,
    REPAIR_PROMPT_VERSION,
    escape_for_prompt,
    render,
)
from docs_rag.synthesis.schema import (
    Chunk,
    Citation,
    Claim,
    QueryResponse,
    QueryTrace,
    SynthesisOutput,
)

_log = structlog.get_logger(__name__)


@dataclass(slots=True)
class Synthesizer:
    settings: Settings
    provider: SynthesisProvider

    async def answer(
        self,
        question: str,
        ranked_chunks: Sequence[RankedChunk],
        *,
        retrieval_ms: int,
        rerank_ms: int,
        retrieval_precision: float,
        cache_hit: bool,
    ) -> QueryResponse:
        if not ranked_chunks:
            return _empty_response(
                question=question,
                retrieval_ms=retrieval_ms,
                rerank_ms=rerank_ms,
                cache_hit=cache_hit,
            )

        chunks = [r.chunk for r in ranked_chunks]
        # Escape untrusted chunk text + question against prompt-template
        # injection (a chunk containing `{{question}}` would otherwise
        # smuggle our literal placeholder into the rendered prompt).
        context_json = json.dumps(
            [
                {
                    "chunk_id": r.chunk.chunk_id,
                    "section_path": r.chunk.section_path,
                    "page": r.chunk.span.page,
                    "text": escape_for_prompt(r.chunk.text),
                    "rerank_score": round(r.rerank_score, 4),
                }
                for r in ranked_chunks
            ],
            ensure_ascii=False,
        )

        system, user = render(
            PROMPT_VERSION,
            question=escape_for_prompt(question),
            context_json=context_json,
        )

        synthesis_started = time.perf_counter()
        try:
            output, _, _ = await self.provider.synthesize(system, user)
        except AnthropicError as exc:
            _log.error(
                "synthesis.provider_error_first_pass",
                question=question[:80],
                error=str(exc),
            )
            result = _refused_result(chunks, reason="synthesis provider error")
            synthesis_ms = int((time.perf_counter() - synthesis_started) * 1000)
            return _response_from(
                question=question,
                result=result,
                chunks=chunks,
                retrieval_ms=retrieval_ms,
                rerank_ms=rerank_ms,
                synthesis_ms=synthesis_ms,
                retrieval_precision=retrieval_precision,
                cache_hit=cache_hit,
            )

        try:
            result = enforce(output, chunks)
        except CitationViolation as violation:
            _log.warning(
                "synthesis.citation_violation_first_pass",
                question=question[:80],
                error=str(violation),
            )
            result = await self._repair(
                question=question,
                context_json=context_json,
                original=output,
                error=str(violation),
                chunks=chunks,
            )
        synthesis_ms = int((time.perf_counter() - synthesis_started) * 1000)

        return _response_from(
            question=question,
            result=result,
            chunks=chunks,
            retrieval_ms=retrieval_ms,
            rerank_ms=rerank_ms,
            synthesis_ms=synthesis_ms,
            retrieval_precision=retrieval_precision,
            cache_hit=cache_hit,
        )

    async def _repair(
        self,
        *,
        question: str,
        context_json: str,
        original: SynthesisOutput,
        error: str,
        chunks: list[Chunk],
    ) -> EnforcementResult:
        valid_ids = json.dumps([c.chunk_id for c in chunks])
        original_json = original.model_dump_json()
        system, user = render(
            REPAIR_PROMPT_VERSION,
            question=escape_for_prompt(question),
            context_json=context_json,
            original=original_json,
            error=escape_for_prompt(error),
            valid_ids=valid_ids,
        )
        try:
            repaired, _, _ = await self.provider.synthesize(system, user, max_tokens=1024)
            result = enforce(repaired, chunks)
        except CitationViolation as exc:
            _log.error("synthesis.citation_violation_after_repair", error=str(exc))
            return _refused_result(chunks, reason="citation enforcement failed twice")
        except AnthropicError as exc:
            _log.error("synthesis.provider_error_after_repair", error=str(exc))
            return _refused_result(chunks, reason="synthesis provider error during repair")
        return EnforcementResult(
            output=result.output,
            faithfulness_score=result.faithfulness_score,
            repaired=True,
        )


def _response_from(
    *,
    question: str,
    result: EnforcementResult,
    chunks: list[Chunk],
    retrieval_ms: int,
    rerank_ms: int,
    synthesis_ms: int,
    retrieval_precision: float,
    cache_hit: bool,
) -> QueryResponse:
    chunks_by_id = {c.chunk_id: c for c in chunks}
    cited_ids: list[str] = []
    seen: set[str] = set()
    for claim in result.output.claims:
        for cid in claim.chunk_ids:
            if cid not in seen and cid in chunks_by_id:
                cited_ids.append(cid)
                seen.add(cid)

    citations = [
        Citation(
            chunk_id=cid,
            document_id=chunks_by_id[cid].document_id,
            page=chunks_by_id[cid].span.page,
            snippet=chunks_by_id[cid].text[:240],
        )
        for cid in cited_ids
    ]

    _trace = current_trace()
    cost_usd = _trace.total_cost_usd if _trace is not None else 0.0
    total_ms = retrieval_ms + rerank_ms + synthesis_ms
    return QueryResponse(
        question=question,
        answer_markdown=result.output.answer_markdown,
        citations=citations,
        claims=list(result.output.claims),
        faithfulness_score=round(result.faithfulness_score, 4),
        retrieval_precision=round(retrieval_precision, 4),
        trace=QueryTrace(
            retrieval_ms=retrieval_ms,
            rerank_ms=rerank_ms,
            synthesis_ms=synthesis_ms,
            total_ms=total_ms,
            cost_usd=cost_usd,
            cache_hit=cache_hit,
        ),
    )


def _refused_result(chunks: list[Chunk], *, reason: str) -> EnforcementResult:
    """Build a refused EnforcementResult, used when we cannot ground an answer."""
    msg = "I could not produce a fully grounded answer for this question."
    refused = SynthesisOutput(
        answer_markdown=msg,
        claims=[Claim(text=msg, chunk_ids=[chunks[0].chunk_id])],
        refused=True,
        refusal_reason=reason,
    )
    return EnforcementResult(output=refused, faithfulness_score=0.0, repaired=True)


def _empty_response(
    *,
    question: str,
    retrieval_ms: int,
    rerank_ms: int,
    cache_hit: bool,
) -> QueryResponse:
    msg = "No documents are indexed yet. Upload a PDF or paste a URL to start."
    _trace = current_trace()
    cost_usd = _trace.total_cost_usd if _trace is not None else 0.0
    return QueryResponse(
        question=question,
        answer_markdown=msg,
        citations=[],
        claims=[],
        faithfulness_score=0.0,
        retrieval_precision=0.0,
        trace=QueryTrace(
            retrieval_ms=retrieval_ms,
            rerank_ms=rerank_ms,
            synthesis_ms=0,
            total_ms=retrieval_ms + rerank_ms,
            cost_usd=cost_usd,
            cache_hit=cache_hit,
        ),
    )
