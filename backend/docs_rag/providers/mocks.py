"""Deterministic mock providers used by tests and the demo's offline mode.

Goals:
  - Embeddings: hash-trick bag-of-words vectors. Same text → same vector;
    overlapping vocabulary → high cosine similarity; disjoint vocab →
    near-zero similarity. This keeps the offline demo and unit tests
    semantically faithful (search for "Anthropic Claude assistant" must
    rank a chunk about Claude above one about bicycles).
  - Rerank: simple bag-of-words overlap score over (query, doc).
  - Vector store: in-process dict + brute-force cosine search.
  - Synthesis: emits a valid SynthesisOutput JSON shape that cites the
    first chunk_id passed in. This is enough to exercise the citation
    enforcer end-to-end without burning real tokens.

These mocks are used:
  - When Settings.mock_providers == True
  - In all unit tests that don't use respx cassettes
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from datetime import UTC, datetime

import numpy as np

from docs_rag.synthesis.schema import Chunk, Claim, SynthesisOutput


def _hash_vector(text: str, dim: int) -> list[float]:
    """Bag-of-words hash-trick vector.

    Each token contributes a +1 to a deterministic hashed coordinate. The
    vector is L2-normalized before return so cosine similarity behaves
    sensibly. Empty text yields the zero vector.
    """
    tokens = _tokens(text)
    if not tokens:
        return [0.0] * dim
    raw = np.zeros(dim, dtype=np.float32)
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        raw[index] += sign
    norm = float(np.linalg.norm(raw))
    if norm == 0.0:
        return [0.0] * dim
    normalized: list[float] = (raw / norm).tolist()
    return normalized


class MockEmbeddingProvider:
    def __init__(self, dim: int = 1024) -> None:
        self._dim = dim

    @property
    def dimensions(self) -> int:
        return self._dim

    async def aclose(self) -> None:
        return None

    async def embed_query(self, text: str) -> list[float]:
        return _hash_vector(_normalize(text), self._dim)

    async def embed_chunks_late(
        self, full_text: str, chunk_spans: list[tuple[int, int]]
    ) -> tuple[list[list[float]], int]:
        vectors = [
            _hash_vector(_normalize(full_text[start:end]), self._dim) for start, end in chunk_spans
        ]
        tokens = max(1, len(full_text) // 4)
        return vectors, tokens


class MockRerankProvider:
    async def aclose(self) -> None:
        return None

    async def rerank(self, query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:
        if not documents:
            return []
        q_terms = Counter(_tokens(query))
        scored: list[tuple[int, float]] = []
        for i, doc in enumerate(documents):
            d_terms = Counter(_tokens(doc))
            overlap = sum(min(q_terms[t], d_terms[t]) for t in q_terms)
            denom = max(1, sum(q_terms.values()))
            scored.append((i, overlap / denom))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[: min(top_k, len(scored))]


class MockSynthesisProvider:
    """Returns a SynthesisOutput citing the first chunk_id from `user`.

    `user` must be a JSON-rendered context block with a `chunks` array;
    we extract the first chunk_id with a regex so the mock survives
    minor prompt drift.
    """

    async def aclose(self) -> None:
        return None

    async def synthesize(
        self, system: str, user: str, *, max_tokens: int = 2048
    ) -> tuple[SynthesisOutput, int, int]:
        chunk_ids = re.findall(r'"chunk_id"\s*:\s*"([^"]+)"', user)
        if not chunk_ids:
            chunk_ids = ["mock-chunk-0"]
        first = chunk_ids[0]
        answer = "Based on the retrieved context, the document supports the user's question."
        output = SynthesisOutput(
            answer_markdown=answer,
            claims=[Claim(text=answer, chunk_ids=[first])],
            refused=False,
            refusal_reason=None,
        )
        return output, len(user) // 4, len(answer) // 4


class InMemoryVectorStore:
    """Dict-backed vector store with brute-force cosine search."""

    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}
        self._vectors: dict[str, list[float]] = {}

    async def aclose(self) -> None:
        self._chunks.clear()
        self._vectors.clear()

    async def ensure_collection(self, dimensions: int) -> None:
        return None

    async def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        for chunk, vector in zip(chunks, vectors, strict=True):
            self._chunks[chunk.chunk_id] = chunk
            self._vectors[chunk.chunk_id] = vector

    async def search(
        self,
        vector: list[float],
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[tuple[Chunk, float]]:
        candidates: list[tuple[Chunk, float]] = []
        doc_filter = set(document_ids) if document_ids else None
        for chunk_id, vec in self._vectors.items():
            chunk = self._chunks[chunk_id]
            if doc_filter is not None and chunk.document_id not in doc_filter:
                continue
            score = _cosine(vector, vec)
            candidates.append((chunk, score))
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]

    async def get_chunk(self, chunk_id: str) -> Chunk | None:
        return self._chunks.get(chunk_id)

    async def list_chunks(self, document_id: str) -> list[Chunk]:
        return [c for c in self._chunks.values() if c.document_id == document_id]

    async def scroll_all_chunks(self, *, max_chunks: int | None = None) -> list[Chunk]:
        chunks = list(self._chunks.values())
        if max_chunks is not None:
            return chunks[:max_chunks]
        return chunks

    async def delete_document(self, document_id: str) -> None:
        ids = [cid for cid, c in self._chunks.items() if c.document_id == document_id]
        for cid in ids:
            self._chunks.pop(cid, None)
            self._vectors.pop(cid, None)


def make_mock_chunk(
    chunk_id: str,
    document_id: str,
    text: str,
    page: int = 1,
    char_start: int = 0,
) -> Chunk:
    from docs_rag.synthesis.schema import ChunkSpan

    return Chunk(
        chunk_id=chunk_id,
        document_id=document_id,
        text=text,
        span=ChunkSpan(page=page, char_start=char_start, char_end=char_start + len(text)),
        section_path=[],
        token_count=max(1, math.ceil(len(text) / 4)),
        created_at=datetime.now(UTC),
    )


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize(text: str) -> str:
    return " ".join(_TOKEN_RE.findall(text.lower()))


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
