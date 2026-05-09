"""In-memory BM25 sparse index, scoped per query.

Per-query scope keeps the design simple and correct: we scroll all
chunks for the requested document_ids out of qdrant (qdrant is the
source of truth), build a BM25Okapi index, score, and return the top-k.

This trades latency for correctness, for a single 200-page document
the index builds in <50ms. For multi-hundred-document corpora we'd
swap in a persistent BM25 (e.g., tantivy) but the spec scope is "user
uploads a doc, asks questions about it," so per-query is right.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from docs_rag.synthesis.schema import Chunk

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass(slots=True)
class BM25Result:
    chunk: Chunk
    score: float


class BM25Index:
    """Builds once per query (cheap)."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        if not chunks:
            self._index: BM25Okapi | None = None
            return
        corpus = [tokenize(c.text) for c in chunks]
        self._index = BM25Okapi(corpus)

    def search(self, query: str, top_k: int) -> list[BM25Result]:
        if self._index is None or not self._chunks or top_k <= 0:
            return []
        scores = self._index.get_scores(tokenize(query))
        ranked = sorted(
            zip(self._chunks, scores, strict=True),
            key=lambda x: x[1],
            reverse=True,
        )
        return [
            BM25Result(chunk=chunk, score=float(score))
            for chunk, score in ranked[:top_k]
            if score > 0.0
        ]
