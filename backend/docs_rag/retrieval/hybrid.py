"""Hybrid retrieval orchestrator.

Pipeline (matches the spec exactly):

    BM25(top_k_bm25)  ─┐
                       ├─> RRF ─> Cohere Rerank(top_k_rerank) ─> answer context
    Dense(top_k_dense) ┘

Outputs include a `retrieval_precision` proxy: the share of reranked
chunks whose Cohere score exceeds 0.5. Final scoring (faithfulness vs.
the answer) happens in synthesis.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import structlog

from docs_rag.config import Settings
from docs_rag.providers.base import EmbeddingProvider, RerankProvider, VectorStore
from docs_rag.retrieval.bm25 import BM25Index
from docs_rag.retrieval.rrf import reciprocal_rank_fusion
from docs_rag.synthesis.schema import Chunk

_log = structlog.get_logger(__name__)


@dataclass(slots=True)
class RankedChunk:
    chunk: Chunk
    rerank_score: float


@dataclass(slots=True)
class RetrievalResult:
    chunks: list[RankedChunk]
    retrieval_ms: int
    rerank_ms: int
    retrieval_precision: float


@dataclass(slots=True)
class HybridRetriever:
    settings: Settings
    embedder: EmbeddingProvider
    reranker: RerankProvider
    vector_store: VectorStore

    async def retrieve(
        self,
        query: str,
        *,
        document_ids: list[str] | None = None,
        top_k: int | None = None,
    ) -> RetrievalResult:
        rerank_top_k = top_k or self.settings.rerank_top_k

        retrieval_started = time.perf_counter()
        query_vector = await self.embedder.embed_query(query)
        dense_hits = await self.vector_store.search(
            query_vector,
            top_k=self.settings.retrieval_top_k_dense,
            document_ids=document_ids,
        )
        bm25_corpus = await self._gather_corpus(document_ids, dense_hits)
        bm25_results = BM25Index(bm25_corpus).search(
            query, top_k=self.settings.retrieval_top_k_bm25
        )
        retrieval_ms = int((time.perf_counter() - retrieval_started) * 1000)

        chunk_by_id: dict[str, Chunk] = {c.chunk_id: c for c, _ in dense_hits}
        for r in bm25_results:
            chunk_by_id.setdefault(r.chunk.chunk_id, r.chunk)
        for chunk in bm25_corpus:
            chunk_by_id.setdefault(chunk.chunk_id, chunk)

        dense_ranking = [chunk.chunk_id for chunk, _ in dense_hits]
        bm25_ranking = [r.chunk.chunk_id for r in bm25_results]
        fused = reciprocal_rank_fusion([dense_ranking, bm25_ranking])

        candidate_pool_size = max(rerank_top_k * 4, 16)
        candidate_ids = [cid for cid, _ in fused[:candidate_pool_size]]
        candidate_chunks = [chunk_by_id[cid] for cid in candidate_ids if cid in chunk_by_id]

        if not candidate_chunks:
            return RetrievalResult(
                chunks=[], retrieval_ms=retrieval_ms, rerank_ms=0, retrieval_precision=0.0
            )

        rerank_started = time.perf_counter()
        rerank_pairs = await self.reranker.rerank(
            query, [c.text for c in candidate_chunks], top_k=rerank_top_k
        )
        rerank_ms = int((time.perf_counter() - rerank_started) * 1000)

        ranked = [
            RankedChunk(chunk=candidate_chunks[idx], rerank_score=score)
            for idx, score in rerank_pairs
            if 0 <= idx < len(candidate_chunks)
        ]

        precision = sum(1 for r in ranked if r.rerank_score >= 0.5) / len(ranked) if ranked else 0.0

        _log.info(
            "retrieval.hybrid",
            query_len=len(query),
            dense=len(dense_hits),
            bm25=len(bm25_results),
            fused=len(fused),
            reranked=len(ranked),
            retrieval_ms=retrieval_ms,
            rerank_ms=rerank_ms,
            precision=round(precision, 3),
        )

        return RetrievalResult(
            chunks=ranked,
            retrieval_ms=retrieval_ms,
            rerank_ms=rerank_ms,
            retrieval_precision=precision,
        )

    async def _gather_corpus(
        self,
        document_ids: list[str] | None,
        dense_hits: list[tuple[Chunk, float]],
    ) -> list[Chunk]:
        """Build the BM25 candidate set.

        - When document_ids is given, BM25 over the full doc(s).
        - Otherwise, BM25 over the entire indexed corpus (paginated scroll
          from Qdrant). Earlier versions of this method scored BM25 only
          over the dense top-K, which silently degraded to "rerank dense by
          sparse score", defeating the lexical-recall property of hybrid
          retrieval. The cap is intentional: callers can override
          `bm25_corpus_max_chunks` in settings if their corpora outgrow the
          page-budget envelope (~10K chunks ≈ 10 MB BM25 index).
        """
        if document_ids:
            collected: list[Chunk] = []
            for doc_id in document_ids:
                collected.extend(await self.vector_store.list_chunks(doc_id))
            return collected
        max_chunks = self.settings.bm25_corpus_max_chunks
        corpus = await self.vector_store.scroll_all_chunks(max_chunks=max_chunks)
        # Always include any dense hits even if they fell outside the cap;
        # they're guaranteed-relevant.
        seen = {c.chunk_id for c in corpus}
        for chunk, _ in dense_hits:
            if chunk.chunk_id not in seen:
                corpus.append(chunk)
        return corpus
