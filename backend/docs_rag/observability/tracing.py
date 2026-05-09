"""Per-call cost + latency tracing.

Every external call (embed, rerank, synthesize) is wrapped in `traced(...)`
which records duration, token counts, and a USD cost. The trace is attached
to structlog contextvars so a single request's logs share a request_id.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

import structlog

_log = structlog.get_logger(__name__)
_current_trace: ContextVar[RequestTrace | None] = ContextVar("_current_trace", default=None)


@dataclass(slots=True)
class CallRecord:
    name: str
    duration_ms: int
    cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RequestTrace:
    request_id: str
    started_at: float
    calls: list[CallRecord] = field(default_factory=list)

    @property
    def total_cost_usd(self) -> float:
        return round(sum(c.cost_usd for c in self.calls), 6)

    @property
    def total_ms(self) -> int:
        return int((time.perf_counter() - self.started_at) * 1000)

    def add(self, record: CallRecord) -> None:
        self.calls.append(record)


@contextmanager
def request_scope(request_id: str | None = None) -> Iterator[RequestTrace]:
    trace = RequestTrace(
        request_id=request_id or uuid.uuid4().hex[:12],
        started_at=time.perf_counter(),
    )
    token = _current_trace.set(trace)
    structlog.contextvars.bind_contextvars(request_id=trace.request_id)
    try:
        yield trace
    finally:
        _current_trace.reset(token)
        structlog.contextvars.unbind_contextvars("request_id")


def current_trace() -> RequestTrace | None:
    return _current_trace.get()


@contextmanager
def traced(name: str, *, cost_usd: float = 0.0, **metadata: Any) -> Iterator[CallRecord]:
    """Context manager that records one external/expensive call."""
    start = time.perf_counter()
    record = CallRecord(name=name, duration_ms=0, cost_usd=cost_usd, metadata=metadata)
    try:
        yield record
    finally:
        record.duration_ms = int((time.perf_counter() - start) * 1000)
        if (trace := current_trace()) is not None:
            trace.add(record)
        _log.debug(
            "trace.call",
            name=record.name,
            duration_ms=record.duration_ms,
            cost_usd=round(record.cost_usd, 6),
            **record.metadata,
        )
