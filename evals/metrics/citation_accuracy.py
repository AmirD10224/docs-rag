"""citation_accuracy: do cited chunks actually contain the expected anchor?

A claim is "citation-accurate" if at least one of its cited chunk_ids
points to a chunk whose text contains at least one of the expected
`relevant_anchors` (case-insensitive substring match).

We use anchor substrings rather than chunk_id equality so the metric
remains stable as the chunker is tuned. The downside is that a
generic anchor (e.g., "the company") would inflate the score; the
maintainer pass on `golden_set.jsonl` is what guards against that.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CitationAccuracyResult:
    accurate: int
    total: int

    @property
    def value(self) -> float:
        return 0.0 if self.total == 0 else self.accurate / self.total


def score_citation_accuracy(cited_chunk_texts: list[str], anchors: list[str]) -> bool:
    """True if any cited chunk contains any anchor (case-insensitive)."""
    if not cited_chunk_texts or not anchors:
        return False
    haystack = "\n".join(t.lower() for t in cited_chunk_texts)
    return any(anchor.lower() in haystack for anchor in anchors)


def aggregate(rows: list[bool]) -> CitationAccuracyResult:
    return CitationAccuracyResult(accurate=sum(rows), total=len(rows))
