"""Tests for the eval-gate diff logic.

These tests prove the gate actually blocks on regression. They are the
substrate for `docs/evidence.png`, until a real PR triggers the gate,
the test suite is the credibility artifact for the "merges blocked on
regression" claim.
"""

from __future__ import annotations

from typing import Any

from evals.diff import render


def _report(scores: dict[str, float]) -> dict[str, Any]:
    return {
        "git_sha": "abc1234",
        "created_at": "2026-05-06T00:00:00Z",
        "scores": [{"metric": k, "value": v, "n": 50} for k, v in scores.items()],
        "golden_set_size": 50,
        "duration_seconds": 12.0,
        "cost_usd": 0.05,
    }


def test_gate_passes_when_metrics_unchanged() -> None:
    base = _report({"faithfulness": 0.92, "citation_accuracy": 0.88})
    head = _report({"faithfulness": 0.92, "citation_accuracy": 0.88})
    body, blocked = render(base, head)
    assert blocked is False
    assert "✅" in body


def test_gate_passes_when_metrics_improve() -> None:
    base = _report({"faithfulness": 0.82, "citation_accuracy": 0.78})
    head = _report({"faithfulness": 0.91, "citation_accuracy": 0.85})
    _body, blocked = render(base, head)
    assert blocked is False


def test_gate_blocks_on_faithfulness_regression() -> None:
    base = _report({"faithfulness": 0.92, "citation_accuracy": 0.88})
    head = _report({"faithfulness": 0.85, "citation_accuracy": 0.88})  # -7pt
    body, blocked = render(base, head)
    assert blocked is True
    assert "regression" in body  # body asserted for the message check


def test_gate_blocks_on_citation_accuracy_regression() -> None:
    base = _report({"faithfulness": 0.90, "citation_accuracy": 0.88})
    head = _report({"faithfulness": 0.90, "citation_accuracy": 0.80})  # -8pt
    _body, blocked = render(base, head)
    assert blocked is True


def test_gate_tolerates_within_threshold() -> None:
    """A 2-point drop should not block, the threshold is 3 points."""
    base = _report({"faithfulness": 0.90, "citation_accuracy": 0.88})
    head = _report({"faithfulness": 0.88, "citation_accuracy": 0.86})  # both -2pt
    _body, blocked = render(base, head)
    assert blocked is False


def test_diff_table_renders_metric_rows() -> None:
    base = _report({"faithfulness": 0.90, "citation_accuracy": 0.88})
    head = _report({"faithfulness": 0.92, "citation_accuracy": 0.85})
    body, _ = render(base, head)
    assert "faithfulness" in body
    assert "citation_accuracy" in body
    assert "0.9000" in body  # base value rendered
