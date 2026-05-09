"""Dependency container.

We keep DI simple, no fastapi.Depends magic per-request. The container
is built once at app startup and stored on `app.state.container`. Each
request handler reaches for `request.app.state.container.synthesizer`,
etc. Tests build a `Container` directly with mock providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from docs_rag.config import Settings
from docs_rag.ingest.pipeline import IngestPipeline
from docs_rag.observability.cache import Cache, InMemoryCache, RedisCache
from docs_rag.observability.cost_guard import CostGuard
from docs_rag.providers.base import (
    EmbeddingProvider,
    RerankProvider,
    SynthesisProvider,
    VectorStore,
)
from docs_rag.providers.mocks import (
    InMemoryVectorStore,
    MockEmbeddingProvider,
    MockRerankProvider,
    MockSynthesisProvider,
)
from docs_rag.retrieval.hybrid import HybridRetriever
from docs_rag.synthesis.synthesizer import Synthesizer


class Closeable(Protocol):
    async def aclose(self) -> None: ...


@dataclass(slots=True)
class Container:
    settings: Settings
    embedder: EmbeddingProvider
    reranker: RerankProvider
    synthesis: SynthesisProvider
    vector_store: VectorStore
    cache: Cache
    pipeline: IngestPipeline
    retriever: HybridRetriever
    synthesizer: Synthesizer
    cost_guard: CostGuard

    async def aclose(self) -> None:
        for component in (
            self.embedder,
            self.reranker,
            self.synthesis,
            self.vector_store,
            self.cache,
        ):
            close = getattr(component, "aclose", None)
            if callable(close):
                await close()


def build_container(settings: Settings) -> Container:
    """Wire concrete providers based on settings.mock_providers."""
    if settings.mock_providers:
        embedder: EmbeddingProvider = MockEmbeddingProvider(dim=settings.embedding_dimensions)
        reranker: RerankProvider = MockRerankProvider()
        synthesis: SynthesisProvider = MockSynthesisProvider()
        vector_store: VectorStore = InMemoryVectorStore()
        cache: Cache = InMemoryCache()
    else:
        from docs_rag.providers.anthropic import AnthropicClient
        from docs_rag.providers.cohere import CohereRerankClient
        from docs_rag.providers.jina import JinaEmbeddingClient
        from docs_rag.providers.qdrant import QdrantStore

        embedder = JinaEmbeddingClient(settings)
        reranker = CohereRerankClient(settings)
        synthesis = AnthropicClient(settings)
        vector_store = QdrantStore(settings)
        cache = (
            RedisCache.from_url(settings.redis_url, socket_timeout=settings.redis_timeout_seconds)
            if settings.redis_url
            else InMemoryCache()
        )

    pipeline = IngestPipeline(
        embedder=embedder,
        vector_store=vector_store,
        url_max_bytes=settings.url_fetch_max_bytes,
        url_timeout_seconds=settings.url_fetch_timeout_seconds,
    )
    retriever = HybridRetriever(
        settings=settings,
        embedder=embedder,
        reranker=reranker,
        vector_store=vector_store,
    )
    synthesizer = Synthesizer(settings=settings, provider=synthesis)
    cost_guard = CostGuard(cap_usd=settings.daily_cost_cap_usd)
    return Container(
        settings=settings,
        embedder=embedder,
        reranker=reranker,
        synthesis=synthesis,
        vector_store=vector_store,
        cache=cache,
        pipeline=pipeline,
        retriever=retriever,
        synthesizer=synthesizer,
        cost_guard=cost_guard,
    )
