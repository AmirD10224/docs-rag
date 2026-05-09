from __future__ import annotations

from docs_rag.config import Settings
from docs_rag.observability.pricing import claude_cost, cohere_rerank_cost, jina_cost


def test_claude_cost_uses_input_and_output_rates() -> None:
    s = Settings(price_claude_input_per_mtok=3.0, price_claude_output_per_mtok=15.0)
    cost = claude_cost(1_000_000, 1_000_000, s)
    assert round(cost, 2) == 18.00


def test_jina_cost_per_million() -> None:
    s = Settings(price_jina_per_mtok=0.20)
    assert round(jina_cost(2_000_000, s), 4) == 0.40


def test_cohere_rerank_cost_per_thousand_calls() -> None:
    s = Settings(price_cohere_rerank_per_1k=2.0)
    assert round(cohere_rerank_cost(1000, s), 4) == 2.0


def test_zero_inputs_zero_cost() -> None:
    s = Settings()
    assert claude_cost(0, 0, s) == 0.0
    assert jina_cost(0, s) == 0.0
    assert cohere_rerank_cost(0, s) == 0.0
