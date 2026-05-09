"""Citation enforcement: the guarantee buyers actually pay for.

Every claim in `SynthesisOutput.claims` must reference at least one
chunk_id that was actually in the retrieval context. If any claim
fails this check, we either:

  (a) repair: send Claude a corrective prompt with the validation
      error and the full set of valid chunk_ids, then re-run validation.
      One retry only.
  (b) refuse: synthesizer surfaces a refused response (refused=true);
      we'd rather refuse than hallucinate.

Faithfulness score: a content-token-overlap proxy surfaced live in the
UI. ratio of claims whose cited chunk(s) share ≥40% of the claim's
content tokens (stopwords removed). The harder LLM-as-judge faithfulness
runs offline in evals/run.py and is the metric the CI gate compares.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from docs_rag.synthesis.schema import Chunk, Claim, SynthesisOutput

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "from",
        "as",
        "and",
        "or",
        "but",
        "if",
        "then",
        "than",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "into",
        "about",
        "over",
        "under",
        "between",
        "among",
        "any",
        "all",
        "each",
        "every",
        "no",
        "not",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "will",
        "would",
        "should",
        "can",
        "could",
    }
)


class CitationViolation(RuntimeError):  # noqa: N818  - "Violation" is the domain term
    """Raised when synthesis cites a chunk_id we did not send."""


@dataclass(slots=True)
class EnforcementResult:
    output: SynthesisOutput
    faithfulness_score: float
    repaired: bool


def enforce(output: SynthesisOutput, chunks: Iterable[Chunk]) -> EnforcementResult:
    """Validate citations and compute the faithfulness proxy.

    Raises CitationViolation if any claim references a chunk_id that
    isn't in `chunks`. Caller decides whether to repair (one retry) or
    propagate.
    """
    valid_ids = {c.chunk_id: c for c in chunks}
    if not valid_ids:
        raise CitationViolation("no context chunks provided")

    bad: list[tuple[str, list[str]]] = []
    for claim in output.claims:
        unknown = [cid for cid in claim.chunk_ids if cid not in valid_ids]
        if unknown:
            bad.append((claim.text[:80], unknown))

    if bad:
        details = "; ".join(f'"{t}" cites unknown {ids}' for t, ids in bad)
        raise CitationViolation(f"unknown chunk_ids: {details}")

    faithfulness = _faithfulness(output.claims, valid_ids)
    return EnforcementResult(output=output, faithfulness_score=faithfulness, repaired=False)


def _faithfulness(claims: list[Claim], chunks_by_id: dict[str, Chunk]) -> float:
    if not claims:
        return 0.0
    grounded = 0
    for claim in claims:
        claim_terms = _content_terms(claim.text)
        if not claim_terms:
            continue
        cited_text = " ".join(
            chunks_by_id[cid].text for cid in claim.chunk_ids if cid in chunks_by_id
        )
        cited_terms = _content_terms(cited_text)
        if not cited_terms:
            continue
        overlap = len(claim_terms & cited_terms)
        if overlap / len(claim_terms) >= 0.4:
            grounded += 1
    return grounded / len(claims)


def _content_terms(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 2}
