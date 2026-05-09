from __future__ import annotations

from docs_rag.providers.mocks import make_mock_chunk
from docs_rag.retrieval.bm25 import BM25Index


def test_bm25_finds_relevant_chunk() -> None:
    chunks = [
        make_mock_chunk("c-0", "doc1", "Cats are independent animals that purr."),
        make_mock_chunk(
            "c-1",
            "doc1",
            "Anthropic builds Claude. Claude is an AI assistant.",
        ),
        make_mock_chunk("c-2", "doc1", "Bicycles have two wheels and pedals."),
    ]
    index = BM25Index(chunks)
    results = index.search("anthropic claude assistant", top_k=2)
    assert results
    assert results[0].chunk.chunk_id == "c-1"


def test_bm25_zero_score_filtered() -> None:
    chunks = [make_mock_chunk("only", "doc1", "This text contains nothing of interest.")]
    index = BM25Index(chunks)
    results = index.search("zzzzz qqqq", top_k=5)
    assert results == []


def test_bm25_empty_corpus() -> None:
    index = BM25Index([])
    assert index.search("anything", top_k=5) == []
