"""Qdrant vector store wrapper.

Schema decisions:
  - Each chunk_id becomes a deterministic UUID5 in the qdrant point id
    (qdrant requires uuid or int ids; chunk_ids are arbitrary strings).
  - Chunk metadata is duplicated into the point payload so we can
    reconstruct citations without a second round-trip.
  - We use cosine distance; Jina v3 vectors are L2-normalized.

Filtering by document_id uses a `must` payload condition.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qm

from docs_rag.config import Settings
from docs_rag.observability.tracing import traced
from docs_rag.synthesis.schema import Chunk, ChunkSpan

_log = structlog.get_logger(__name__)
_CHUNK_NAMESPACE = uuid.UUID("ad8e2c4e-9f7c-4a8a-b2e4-6e2b9b5d4f10")


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(_CHUNK_NAMESPACE, chunk_id))


class QdrantStore:
    def __init__(
        self,
        settings: Settings,
        *,
        client: AsyncQdrantClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value() or None,
            timeout=int(settings.qdrant_timeout_seconds),
        )
        self._collection = settings.qdrant_collection
        self._collection_ready = False

    async def aclose(self) -> None:
        await self._client.close()

    async def ensure_collection(self, dimensions: int) -> None:
        if self._collection_ready:
            return
        existing = await self._client.collection_exists(self._collection)
        if not existing:
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=qm.VectorParams(size=dimensions, distance=qm.Distance.COSINE),
            )
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name="document_id",
                field_schema=qm.PayloadSchemaType.KEYWORD,
            )
        self._collection_ready = True

    async def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must be same length")
        await self.ensure_collection(self._settings.embedding_dimensions)

        points = [
            qm.PointStruct(
                id=_point_id(chunk.chunk_id),
                vector=vector,
                payload=_chunk_to_payload(chunk),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        with traced("vector.upsert", count=len(points)):
            await self._client.upsert(collection_name=self._collection, points=points, wait=True)

    async def search(
        self,
        vector: list[float],
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[tuple[Chunk, float]]:
        await self.ensure_collection(self._settings.embedding_dimensions)
        flt: qm.Filter | None = None
        if document_ids:
            flt = qm.Filter(
                must=[qm.FieldCondition(key="document_id", match=qm.MatchAny(any=document_ids))]
            )

        with traced("vector.search", top_k=top_k, filtered=bool(document_ids)):
            response = await self._client.query_points(
                collection_name=self._collection,
                query=vector,
                limit=top_k,
                query_filter=flt,
                with_payload=True,
            )
        return [(_payload_to_chunk(p.payload or {}), float(p.score)) for p in response.points]

    async def get_chunk(self, chunk_id: str) -> Chunk | None:
        await self.ensure_collection(self._settings.embedding_dimensions)
        records = await self._client.retrieve(
            collection_name=self._collection,
            ids=[_point_id(chunk_id)],
            with_payload=True,
        )
        if not records:
            return None
        return _payload_to_chunk(records[0].payload or {})

    async def list_chunks(self, document_id: str) -> list[Chunk]:
        await self.ensure_collection(self._settings.embedding_dimensions)
        flt = qm.Filter(
            must=[qm.FieldCondition(key="document_id", match=qm.MatchValue(value=document_id))]
        )
        return await self._scroll(flt)

    async def scroll_all_chunks(self, *, max_chunks: int | None = None) -> list[Chunk]:
        """Scroll the entire collection. Used by hybrid retrieval to feed BM25
        the full corpus rather than only the dense top-K (which would defeat
        the lexical-recall property of hybrid search).

        `max_chunks` puts a soft ceiling on memory cost for very large corpora.
        """
        await self.ensure_collection(self._settings.embedding_dimensions)
        return await self._scroll(None, max_chunks=max_chunks)

    async def _scroll(self, flt: qm.Filter | None, *, max_chunks: int | None = None) -> list[Chunk]:
        chunks: list[Chunk] = []
        # Qdrant's scroll offset is a point id whose union type drifts across
        # SDK versions; we accept whatever it hands back.
        offset: object = None
        page_size = 256
        while True:
            records, offset = await self._client.scroll(
                collection_name=self._collection,
                scroll_filter=flt,
                limit=page_size,
                offset=offset,  # type: ignore[arg-type]
                with_payload=True,
                with_vectors=False,
            )
            chunks.extend(_payload_to_chunk(r.payload or {}) for r in records)
            if offset is None:
                break
            if max_chunks is not None and len(chunks) >= max_chunks:
                return chunks[:max_chunks]
        return chunks

    async def delete_document(self, document_id: str) -> None:
        flt = qm.Filter(
            must=[qm.FieldCondition(key="document_id", match=qm.MatchValue(value=document_id))]
        )
        with traced("vector.delete", document_id=document_id):
            await self._client.delete(
                collection_name=self._collection,
                points_selector=qm.FilterSelector(filter=flt),
                wait=True,
            )


def _chunk_to_payload(chunk: Chunk) -> dict[str, object]:
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "text": chunk.text,
        "page": chunk.span.page,
        "char_start": chunk.span.char_start,
        "char_end": chunk.span.char_end,
        "section_path": list(chunk.section_path),
        "token_count": chunk.token_count,
        "created_at": chunk.created_at.isoformat(),
    }


def _coerce_int(value: object, *, field: str) -> int:
    """Coerce a payload field to int with a clear error message.

    Qdrant payloads are typed as `dict[str, object]` so every read has to
    funnel through a narrowing step; doing it explicitly here keeps mypy
    strict happy without scattered `# type: ignore`s.
    """
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"qdrant payload field {field!r} is not int-coercible: {value!r}")
    return int(value)


def _payload_to_chunk(payload: dict[str, object]) -> Chunk:
    created_raw = payload.get("created_at")
    created_at = (
        datetime.fromisoformat(created_raw) if isinstance(created_raw, str) else datetime.now(UTC)
    )
    section_raw = payload.get("section_path") or []
    section_path = (
        [str(s) for s in cast(list[object], section_raw)] if isinstance(section_raw, list) else []
    )
    return Chunk(
        chunk_id=str(payload["chunk_id"]),
        document_id=str(payload["document_id"]),
        text=str(payload["text"]),
        span=ChunkSpan(
            page=_coerce_int(payload["page"], field="page"),
            char_start=_coerce_int(payload["char_start"], field="char_start"),
            char_end=_coerce_int(payload["char_end"], field="char_end"),
        ),
        section_path=section_path,
        token_count=_coerce_int(payload["token_count"], field="token_count"),
        created_at=created_at,
    )
