"""Eval metric primitives.

The eval directory is not a Python package on the import path, so we
skip these tests when it can't be imported (CI sets PYTHONPATH).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from evals.metrics.calibration import cohens_kappa
from evals.metrics.citation_accuracy import (
    aggregate,
    score_citation_accuracy,
)


def test_citation_accuracy_anchor_match() -> None:
    assert score_citation_accuracy(["The total revenue was $391.0 billion."], ["391.0"]) is True


def test_citation_accuracy_case_insensitive() -> None:
    assert score_citation_accuracy(["The TOTAL was 391."], ["total"]) is True


def test_citation_accuracy_missing_anchor() -> None:
    assert score_citation_accuracy(["unrelated text"], ["391.0"]) is False


def test_citation_accuracy_empty_inputs() -> None:
    assert score_citation_accuracy([], ["x"]) is False
    assert score_citation_accuracy(["x"], []) is False


def test_citation_accuracy_aggregate_value() -> None:
    res = aggregate([True, False, True, True])
    assert res.accurate == 3
    assert res.total == 4
    assert res.value == 0.75


def test_kappa_perfect_agreement() -> None:
    h = ["supported", "partial", "unsupported"]
    assert cohens_kappa(h, list(h)) == 1.0


def test_kappa_disagreement_lower_than_perfect() -> None:
    h = ["supported", "supported", "partial"]
    j = ["supported", "partial", "supported"]
    kappa = cohens_kappa(h, j)
    assert kappa < 1.0


def test_kappa_zero_length_returns_zero() -> None:
    assert cohens_kappa([], []) == 0.0


def test_kappa_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        cohens_kappa(["a"], ["a", "b"])
