"""End-to-end ingest orchestration: parse → late-chunk → embed → upsert.

Public entrypoints:
  - ingest_pdf_bytes(data, title)
  - ingest_url(url)

Both return an IngestResponse and persist chunks into the configured
vector store. The function is stateless and re-entrant: re-ingesting
the same content (same content_hash + title) yields the same
document_id and chunk_ids, so reupload is idempotent at the qdrant
upsert level.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import structlog

from docs_rag.ingest.chunk import (
    ChunkPlan,
    content_hash,
    make_document_id,
    materialize,
    plan_chunks,
)
from docs_rag.ingest.parse import (
    ParsedDocument,
    parse_pdf_bytes,
    parse_url,
)
from docs_rag.observability.tracing import current_trace
from docs_rag.providers.base import EmbeddingProvider, VectorStore
from docs_rag.synthesis.schema import Chunk, IngestResponse

_log = structlog.get_logger(__name__)


@dataclass(slots=True)
class IngestPipeline:
    embedder: EmbeddingProvider
    vector_store: VectorStore
    url_max_bytes: int = 25 * 1024 * 1024
    url_timeout_seconds: float = 15.0

    async def ingest_pdf_bytes(self, data: bytes, *, title: str | None = None) -> IngestResponse:
        parsed = await parse_pdf_bytes(data, title=title)
        return await self._finalize(parsed, content_hash(data))

    async def ingest_url(self, url: str) -> IngestResponse:
        parsed = await parse_url(
            url,
            max_bytes=self.url_max_bytes,
            timeout_seconds=self.url_timeout_seconds,
        )
        return await self._finalize(parsed, content_hash(parsed.text.encode("utf-8")))

    async def _finalize(self, parsed: ParsedDocument, hash_hex: str) -> IngestResponse:
        started = time.perf_counter()
        document_id = make_document_id(parsed.title, hash_hex)
        plans = plan_chunks(document_id, parsed)
        if not plans:
            raise ValueError("document produced zero chunks (too short or empty)")

        chunks = materialize(plans, document_id)
        vectors = await self._embed(parsed, plans)
        await self.vector_store.upsert(chunks, vectors)

        duration_ms = int((time.perf_counter() - started) * 1000)
        trace = current_trace()
        cost_usd = trace.total_cost_usd if trace is not None else 0.0
        _log.info(
            "ingest.completed",
            document_id=document_id,
            chunks=len(chunks),
            pages=parsed.page_count,
            duration_ms=duration_ms,
            cost_usd=cost_usd,
        )
        return IngestResponse(
            document_id=document_id,
            title=parsed.title,
            chunk_count=len(chunks),
            pages=parsed.page_count,
            duration_ms=duration_ms,
            cost_usd=cost_usd,
        )

    async def _embed(self, parsed: ParsedDocument, plans: list[ChunkPlan]) -> list[list[float]]:
        spans = [(plan.span.char_start, plan.span.char_end) for plan in plans]
        vectors, _tokens = await self.embedder.embed_chunks_late(parsed.text, spans)
        if len(vectors) != len(plans):
            raise RuntimeError(f"embedder returned {len(vectors)} vectors for {len(plans)} chunks")
        return vectors

    async def list_document_chunks(self, document_id: str) -> list[Chunk]:
        return await self.vector_store.list_chunks(document_id)
