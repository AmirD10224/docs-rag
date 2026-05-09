"""Unit tests for the daily cost circuit breaker."""

from __future__ import annotations

import pytest

from docs_rag.observability.cost_guard import CostCapExceeded, CostGuard


@pytest.mark.asyncio
async def test_records_cost_under_cap() -> None:
    guard = CostGuard(cap_usd=10.0)
    await guard.check_and_record(2.0)
    await guard.check_and_record(3.0)
    spent, cap = await guard.snapshot()
    assert (spent, cap) == (5.0, 10.0)


@pytest.mark.asyncio
async def test_raises_when_over_cap() -> None:
    guard = CostGuard(cap_usd=1.0)
    await guard.check_and_record(0.7)
    with pytest.raises(CostCapExceeded):
        await guard.check_and_record(0.5)


@pytest.mark.asyncio
async def test_resets_on_new_day(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime, timedelta

    import docs_rag.observability.cost_guard as mod

    base = datetime(2026, 5, 6, 23, 30, tzinfo=UTC)

    class _Clock:
        now = base

    def _datetime_now(tz: object) -> datetime:
        _ = tz
        return _Clock.now

    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:  # type: ignore[override]
            return _datetime_now(tz)

    monkeypatch.setattr(mod, "datetime", _FakeDatetime)

    guard = CostGuard(cap_usd=1.0)
    await guard.check_and_record(0.9)
    # Advance past midnight UTC
    _Clock.now = base + timedelta(hours=1)
    await guard.check_and_record(0.9)  # should not raise, new day resets
    spent, _ = await guard.snapshot()
    assert spent == pytest.approx(0.9)
