from __future__ import annotations

import pytest

from docs_rag.config import Settings
from docs_rag.providers.mocks import (
    InMemoryVectorStore,
    MockEmbeddingProvider,
    MockRerankProvider,
    make_mock_chunk,
)
from docs_rag.retrieval.hybrid import HybridRetriever
from docs_rag.synthesis.schema import Chunk


@pytest.mark.asyncio
async def test_hybrid_returns_ranked_chunks(settings: Settings) -> None:
    embedder = MockEmbeddingProvider(dim=settings.embedding_dimensions)
    store = InMemoryVectorStore()
    chunks: list[Chunk] = [
        make_mock_chunk("c0", "d1", "Anthropic builds Claude, an AI assistant."),
        make_mock_chunk("c1", "d1", "Bicycles have two wheels and pedals."),
        make_mock_chunk("c2", "d1", "Claude is good at reasoning and coding."),
    ]
    vectors, _ = await embedder.embed_chunks_late(
        " ".join(c.text for c in chunks), [(0, 50), (50, 100), (100, 150)]
    )
    await store.upsert(chunks, vectors)

    retriever = HybridRetriever(
        settings=settings,
        embedder=embedder,
        reranker=MockRerankProvider(),
        vector_store=store,
    )
    result = await retriever.retrieve("Anthropic Claude assistant", document_ids=["d1"])
    assert result.chunks
    top_id = result.chunks[0].chunk.chunk_id
    assert top_id in {"c0", "c2"}
    assert 0.0 <= result.retrieval_precision <= 1.0


@pytest.mark.asyncio
async def test_hybrid_empty_store_returns_empty(settings: Settings) -> None:
    embedder = MockEmbeddingProvider(dim=settings.embedding_dimensions)
    retriever = HybridRetriever(
        settings=settings,
        embedder=embedder,
        reranker=MockRerankProvider(),
        vector_store=InMemoryVectorStore(),
    )
    result = await retriever.retrieve("anything")
    assert result.chunks == []
    assert result.retrieval_precision == 0.0
