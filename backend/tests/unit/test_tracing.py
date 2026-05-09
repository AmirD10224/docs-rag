from __future__ import annotations

from docs_rag.observability.tracing import current_trace, request_scope, traced


def test_traced_records_call_in_scope() -> None:
    with request_scope() as trace, traced("op", cost_usd=0.001, foo="bar"):
        pass
    assert len(trace.calls) == 1
    record = trace.calls[0]
    assert record.name == "op"
    assert record.metadata["foo"] == "bar"
    assert record.duration_ms >= 0


def test_total_cost_sum() -> None:
    with request_scope() as trace:
        with traced("a", cost_usd=0.10):
            pass
        with traced("b", cost_usd=0.05):
            pass
    assert round(trace.total_cost_usd, 4) == 0.15


def test_no_scope_does_not_crash() -> None:
    assert current_trace() is None
    with traced("op"):
        pass
