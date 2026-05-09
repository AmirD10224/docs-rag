"""Integration tests for QdrantStore using a fake AsyncQdrantClient.

The fake records the calls QdrantStore makes and returns deterministic
results. This covers the production-path code that was at 0% coverage:
  - upsert (chunk → point payload round-trip)
  - search (filter, score)
  - get_chunk
  - list_chunks (per-document scroll)
  - scroll_all_chunks (corpus-wide scroll, the BM25 corpus path)
  - delete_document
  - _payload_to_chunk coercion (datetime, ints)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import SecretStr

from docs_rag.config import Settings
from docs_rag.providers.qdrant import QdrantStore
from docs_rag.synthesis.schema import Chunk, ChunkSpan


def _make_settings() -> Settings:
    return Settings(
        qdrant_url="http://fake:6333",
        qdrant_api_key=SecretStr(""),
        qdrant_collection="t",
        embedding_dimensions=64,
    )


def _make_chunk(chunk_id: str, doc_id: str = "doc1", text: str = "hello") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=doc_id,
        text=text,
        span=ChunkSpan(page=1, char_start=0, char_end=len(text)),
        section_path=["intro"],
        token_count=2,
        created_at=datetime.now(UTC),
    )


@dataclass(slots=True)
class _Point:
    payload: dict[str, Any]
    score: float = 0.9
    id: str = ""


@dataclass(slots=True)
class _QueryResult:
    points: list[_Point]


@dataclass(slots=True)
class _Record:
    payload: dict[str, Any]


@dataclass(slots=True)
class _FakeAsyncQdrantClient:
    """Minimal fake matching the surface area QdrantStore actually uses."""

    collections_existing: bool = False
    upserted: list[Any] = field(default_factory=list)
    deleted: list[Any] = field(default_factory=list)
    closed: bool = False
    # Configurable returns
    search_payloads: list[dict[str, Any]] = field(default_factory=list)
    scroll_pages: list[tuple[list[_Record], str | None]] = field(default_factory=list)
    retrieve_payload: dict[str, Any] | None = None

    async def collection_exists(self, _name: str) -> bool:
        return self.collections_existing

    async def create_collection(self, **_kw: Any) -> None:
        self.collections_existing = True

    async def create_payload_index(self, **_kw: Any) -> None:
        return None

    async def upsert(self, *, collection_name: str, points: Any, wait: bool) -> None:
        self.upserted.append((collection_name, list(points), wait))

    async def query_points(
        self, *, collection_name: str, query: Any, limit: int, query_filter: Any, with_payload: bool
    ) -> _QueryResult:
        _ = (collection_name, query, query_filter, with_payload)
        points = [_Point(payload=p) for p in self.search_payloads[:limit]]
        return _QueryResult(points=points)

    async def retrieve(
        self, *, collection_name: str, ids: list[Any], with_payload: bool
    ) -> list[_Record]:
        _ = (collection_name, ids, with_payload)
        if self.retrieve_payload is None:
            return []
        return [_Record(payload=self.retrieve_payload)]

    async def scroll(
        self,
        *,
        collection_name: str,
        scroll_filter: Any,
        limit: int,
        offset: Any,
        with_payload: bool,
        with_vectors: bool,
    ) -> tuple[list[_Record], Any]:
        _ = (collection_name, scroll_filter, limit, offset, with_payload, with_vectors)
        if not self.scroll_pages:
            return [], None
        return self.scroll_pages.pop(0)

    async def delete(self, *, collection_name: str, points_selector: Any, wait: bool) -> None:
        self.deleted.append((collection_name, points_selector, wait))

    async def close(self) -> None:
        self.closed = True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upsert_round_trips_payload() -> None:
    fake = _FakeAsyncQdrantClient(collections_existing=True)
    store = QdrantStore(_make_settings(), client=fake)  # type: ignore[arg-type]
    chunk = _make_chunk("c1")
    await store.upsert([chunk], [[0.1] * 64])
    [(coll, points, wait)] = fake.upserted
    assert coll == "t"
    assert wait is True
    assert points[0].payload["chunk_id"] == "c1"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_returns_chunks_and_scores() -> None:
    fake = _FakeAsyncQdrantClient(
        collections_existing=True,
        search_payloads=[
            {
                "chunk_id": "c1",
                "document_id": "d1",
                "text": "hello world",
                "page": 1,
                "char_start": 0,
                "char_end": 11,
                "section_path": ["intro"],
                "token_count": 3,
                "created_at": datetime.now(UTC).isoformat(),
            }
        ],
    )
    store = QdrantStore(_make_settings(), client=fake)  # type: ignore[arg-type]
    hits = await store.search([0.0] * 64, top_k=5)
    assert len(hits) == 1
    chunk, score = hits[0]
    assert chunk.chunk_id == "c1"
    assert 0 < score <= 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_chunk_returns_none_when_missing() -> None:
    fake = _FakeAsyncQdrantClient(collections_existing=True)
    store = QdrantStore(_make_settings(), client=fake)  # type: ignore[arg-type]
    assert await store.get_chunk("missing") is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_chunk_decodes_payload() -> None:
    payload = {
        "chunk_id": "c2",
        "document_id": "d1",
        "text": "x",
        "page": 1,
        "char_start": 0,
        "char_end": 1,
        "section_path": ["s"],
        "token_count": 1,
        "created_at": datetime.now(UTC).isoformat(),
    }
    fake = _FakeAsyncQdrantClient(collections_existing=True, retrieve_payload=payload)
    store = QdrantStore(_make_settings(), client=fake)  # type: ignore[arg-type]
    chunk = await store.get_chunk("c2")
    assert chunk is not None
    assert chunk.chunk_id == "c2"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scroll_all_chunks_paginates() -> None:
    payload = {
        "chunk_id": "x",
        "document_id": "d",
        "text": "t",
        "page": 1,
        "char_start": 0,
        "char_end": 1,
        "section_path": [],
        "token_count": 1,
        "created_at": datetime.now(UTC).isoformat(),
    }
    pages: list[tuple[list[_Record], str | None]] = [
        ([_Record(payload={**payload, "chunk_id": "a"})], "next"),
        ([_Record(payload={**payload, "chunk_id": "b"})], None),
    ]
    fake = _FakeAsyncQdrantClient(collections_existing=True, scroll_pages=pages)
    store = QdrantStore(_make_settings(), client=fake)  # type: ignore[arg-type]
    chunks = await store.scroll_all_chunks()
    assert [c.chunk_id for c in chunks] == ["a", "b"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scroll_all_chunks_respects_max_chunks() -> None:
    payload = {
        "chunk_id": "x",
        "document_id": "d",
        "text": "t",
        "page": 1,
        "char_start": 0,
        "char_end": 1,
        "section_path": [],
        "token_count": 1,
        "created_at": datetime.now(UTC).isoformat(),
    }
    pages: list[tuple[list[_Record], str | None]] = [
        (
            [_Record(payload={**payload, "chunk_id": f"id{i}"}) for i in range(5)],
            "next",
        )
    ]
    fake = _FakeAsyncQdrantClient(collections_existing=True, scroll_pages=pages)
    store = QdrantStore(_make_settings(), client=fake)  # type: ignore[arg-type]
    chunks = await store.scroll_all_chunks(max_chunks=3)
    assert len(chunks) == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_document_calls_filtered_delete() -> None:
    fake = _FakeAsyncQdrantClient(collections_existing=True)
    store = QdrantStore(_make_settings(), client=fake)  # type: ignore[arg-type]
    await store.delete_document("doc-x")
    assert len(fake.deleted) == 1
    coll, _selector, wait = fake.deleted[0]
    assert coll == "t"
    assert wait is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_aclose_propagates_to_underlying_client() -> None:
    fake = _FakeAsyncQdrantClient(collections_existing=True)
    store = QdrantStore(_make_settings(), client=fake)  # type: ignore[arg-type]
    await store.aclose()
    assert fake.closed is True
