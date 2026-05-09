"""Sanity tests for the mock providers themselves.

The whole test suite depends on these being well-behaved, so we
exercise the seams that matter: deterministic embeddings, vector
store cosine ordering, and rerank ordering.
"""

from __future__ import annotations

import math

import pytest

from docs_rag.providers.mocks import (
    InMemoryVectorStore,
    MockEmbeddingProvider,
    MockRerankProvider,
    MockSynthesisProvider,
    make_mock_chunk,
)
from docs_rag.synthesis.schema import Chunk


@pytest.mark.asyncio
async def test_embed_query_deterministic() -> None:
    e = MockEmbeddingProvider(dim=32)
    a = await e.embed_query("hello world")
    b = await e.embed_query("hello world")
    assert a == b


@pytest.mark.asyncio
async def test_embed_chunks_late_returns_one_per_span() -> None:
    e = MockEmbeddingProvider(dim=16)
    text = "abcdefghij"
    spans = [(0, 5), (5, 10)]
    vectors, tokens = await e.embed_chunks_late(text, spans)
    assert len(vectors) == 2
    assert tokens > 0


@pytest.mark.asyncio
async def test_in_memory_store_search_orders_by_similarity() -> None:
    """The mock embedder is a hash-trick BOW model. Identical token sets
    must produce identical vectors, so a chunk whose text matches the
    query verbatim has to rank above a chunk that shares zero tokens.
    """
    e = MockEmbeddingProvider(dim=128)
    store = InMemoryVectorStore()
    chunks: list[Chunk] = [
        make_mock_chunk("a", "doc", "Anthropic builds Claude assistant."),
        make_mock_chunk("b", "doc", "Bicycles have rubber wheels and pedals."),
        make_mock_chunk("c", "doc", "Anthropic Claude assistant helps engineers."),
    ]
    vectors = [await e.embed_query(c.text) for c in chunks]
    await store.upsert(chunks, vectors)
    query_vec = await e.embed_query("Anthropic Claude assistant")
    hits = await store.search(query_vec, top_k=3)
    # Chunk b shares zero query tokens, it must rank last.
    assert hits[-1][0].chunk_id == "b"
    # Chunks a and c each share all three query tokens, both must rank above b.
    top_ids = {hits[0][0].chunk_id, hits[1][0].chunk_id}
    assert top_ids == {"a", "c"}


@pytest.mark.asyncio
async def test_rerank_returns_at_most_top_k() -> None:
    rr = MockRerankProvider()
    docs = ["unrelated", "Anthropic Claude", "no overlap"]
    out = await rr.rerank("Anthropic Claude", docs, top_k=2)
    assert len(out) == 2
    assert out[0][1] >= out[1][1]


@pytest.mark.asyncio
async def test_mock_synthesis_extracts_chunk_id() -> None:
    s = MockSynthesisProvider()
    user = '{"chunks": [{"chunk_id": "abc"}]}'
    output, in_tokens, out_tokens = await s.synthesize("system", user)
    assert output.claims[0].chunk_ids == ["abc"]
    assert in_tokens > 0
    assert out_tokens > 0
    assert math.isfinite(in_tokens)
