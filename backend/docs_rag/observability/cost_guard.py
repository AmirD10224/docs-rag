"""Daily cost circuit breaker.

Tracks total LLM/embedding/rerank spend within a UTC day. If the running
total exceeds `daily_cost_cap_usd`, all mutating endpoints raise 429 until
the next day. The counter is in-process (per Fly.io machine) on purpose -
this is a defense-in-depth control, not a billing source of truth.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, date, datetime


@dataclass(slots=True)
class CostGuard:
    cap_usd: float
    _spent: float = 0.0
    _day: date = field(default_factory=lambda: datetime.now(UTC).date())
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def check_and_record(self, cost: float) -> None:
        """Add `cost` to the running total. Raises CostCapExceeded if over."""
        async with self._lock:
            today = datetime.now(UTC).date()
            if today != self._day:
                self._spent = 0.0
                self._day = today
            if self._spent + cost > self.cap_usd:
                raise CostCapExceeded(
                    f"daily cost cap ${self.cap_usd:.2f} exceeded "
                    f"(spent=${self._spent:.4f}, requested=${cost:.4f})"
                )
            self._spent += cost

    async def snapshot(self) -> tuple[float, float]:
        async with self._lock:
            return self._spent, self.cap_usd


class CostCapExceeded(RuntimeError):  # noqa: N818  - "Exceeded" is the canonical name
    """Raised when the daily cost cap is reached. Surfaced as HTTP 429."""
