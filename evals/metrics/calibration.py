"""Cohen's kappa for judge↔human agreement.

If kappa < 0.6 we don't trust the judge's verdicts and the run is
flagged in the scorecard ("judge uncalibrated, needs more human
labels"). Kappa is computed only on the rows where a human label
exists in `human_labels.jsonl`.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence


def cohens_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    if len(human) != len(judge):
        raise ValueError("label vectors must be same length")
    n = len(human)
    if n == 0:
        return 0.0

    labels = sorted(set(human) | set(judge))
    if len(labels) <= 1:
        return 1.0  # trivially perfect agreement

    p_o = sum(h == j for h, j in zip(human, judge, strict=True)) / n

    h_counts = Counter(human)
    j_counts = Counter(judge)
    p_e = sum((h_counts[label] / n) * (j_counts[label] / n) for label in labels)

    if p_e == 1.0:
        return 1.0
    return (p_o - p_e) / (1.0 - p_e)
