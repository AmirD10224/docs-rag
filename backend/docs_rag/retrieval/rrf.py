"""Reciprocal Rank Fusion.

RRF is parameter-light and well-behaved across heterogeneous score
distributions (BM25 raw vs, cosine similarity). The standard k=60 from
Cormack et al. (2009) is used.

We accept rankings as ordered lists of `chunk_id`. Output is a list of
(chunk_id, fused_score) sorted descending.
"""

from __future__ import annotations

from collections.abc import Iterable

DEFAULT_K = 60.0


def reciprocal_rank_fusion(
    rankings: Iterable[list[str]], *, k: float = DEFAULT_K
) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
