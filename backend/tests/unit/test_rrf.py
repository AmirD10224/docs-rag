"""Reciprocal Rank Fusion."""

from __future__ import annotations

from docs_rag.retrieval.rrf import reciprocal_rank_fusion


def test_single_ranking_preserves_order() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"]])
    assert [cid for cid, _ in fused] == ["a", "b", "c"]


def test_two_rankings_promote_overlap() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]])
    top_two = [cid for cid, _ in fused[:2]]
    assert set(top_two) == {"a", "b"}


def test_empty_input_is_empty() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_scores_descend() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "c", "a"]])
    scores = [s for _, s in fused]
    assert scores == sorted(scores, reverse=True)
