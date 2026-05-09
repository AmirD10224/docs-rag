"""Provider protocols.

Each external service has a Protocol. The real client implements it; the
test-time mock implements it. Routes/services depend only on the Protocol,
which keeps test seams clean and makes vendor swaps a one-file change.
"""

from __future__ import annotations

from typing import Protocol

from docs_rag.synthesis.schema import Chunk, SynthesisOutput


class ProviderError(RuntimeError):
    """Base class for all provider-side runtime errors.

    Subclassed by `AnthropicError`, etc. Catching `ProviderError` lets a
    caller handle "any provider blew up" without coupling to a specific
    vendor. Network/HTTP layer errors that are recoverable should be
    retried inside the provider; only surface here when they are not.
    """


class SynthesisProviderError(ProviderError):
    """Raised by a SynthesisProvider when it cannot return a parsed output."""


class AnthropicError(SynthesisProviderError):
    """Raised by the Anthropic client when Claude returns non-conforming output."""


class EmbeddingProvider(Protocol):
    """Dense embeddings for late chunking (full-doc encode + per-chunk pool)."""

    @property
    def dimensions(self) -> int: ...

    async def embed_query(self, text: str) -> list[float]: ...

    async def embed_chunks_late(
        self, full_text: str, chunk_spans: list[tuple[int, int]]
    ) -> tuple[list[list[float]], int]:
        """Return (per-chunk embeddings, total tokens consumed).

        `chunk_spans` are character-offset (start, end) pairs into `full_text`.
        Implementations encode the full document once, then mean-pool the
        token embeddings that fall inside each span, this is the late-
        chunking property that preserves cross-section context.
        """
        ...


class RerankProvider(Protocol):
    async def rerank(self, query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
        """Return [(original_index, relevance_score)] sorted desc, length <= top_k."""
        ...


class SynthesisProvider(Protocol):
    async def synthesize(
        self, system: str, user: str, *, max_tokens: int = 2048
    ) -> tuple[SynthesisOutput, int, int]:
        """Return (parsed_output, input_tokens, output_tokens)."""
        ...


class VectorStore(Protocol):
    async def ensure_collection(self, dimensions: int) -> None: ...

    async def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None: ...

    async def search(
        self,
        vector: list[float],
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[tuple[Chunk, float]]: ...

    async def get_chunk(self, chunk_id: str) -> Chunk | None: ...

    async def list_chunks(self, document_id: str) -> list[Chunk]: ...

    async def scroll_all_chunks(self, *, max_chunks: int | None = None) -> list[Chunk]:
        """Return every indexed chunk (paginated). Used by hybrid retrieval
        so BM25 can score against the whole corpus when no doc filter is
        applied. Implementations should bound memory via `max_chunks`."""
        ...

    async def delete_document(self, document_id: str) -> None: ...
