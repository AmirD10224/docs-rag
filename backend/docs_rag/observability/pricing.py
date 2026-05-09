"""Pure functions for converting token/call counts to USD cost.

Kept separate from clients so cost math can be unit-tested without mocks.
Defaults match May 2026 list prices but are overridable via Settings.
"""

from __future__ import annotations

from docs_rag.config import Settings


def claude_cost(input_tokens: int, output_tokens: int, settings: Settings) -> float:
    return round(
        input_tokens / 1_000_000 * settings.price_claude_input_per_mtok
        + output_tokens / 1_000_000 * settings.price_claude_output_per_mtok,
        6,
    )


def jina_cost(input_tokens: int, settings: Settings) -> float:
    return round(input_tokens / 1_000_000 * settings.price_jina_per_mtok, 6)


def cohere_rerank_cost(call_count: int, settings: Settings) -> float:
    return round(call_count / 1_000 * settings.price_cohere_rerank_per_1k, 6)
