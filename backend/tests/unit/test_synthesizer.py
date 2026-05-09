"""Synthesizer + citation enforcement integration."""

from __future__ import annotations

from typing import Any

import pytest

from docs_rag.config import Settings
from docs_rag.providers.mocks import (
    MockSynthesisProvider,
    make_mock_chunk,
)
from docs_rag.retrieval.hybrid import RankedChunk
from docs_rag.synthesis.schema import Claim, SynthesisOutput
from docs_rag.synthesis.synthesizer import Synthesizer


def _ranked(chunks: list[Any]) -> list[RankedChunk]:
    return [RankedChunk(chunk=c, rerank_score=1.0 - 0.1 * i) for i, c in enumerate(chunks)]


@pytest.mark.asyncio
async def test_synthesizer_produces_response_with_citations(settings: Settings) -> None:
    provider = MockSynthesisProvider()
    synthesizer = Synthesizer(settings=settings, provider=provider)
    chunks = [make_mock_chunk("c0", "doc", "Anthropic builds Claude.")]

    response = await synthesizer.answer(
        question="Who builds Claude?",
        ranked_chunks=_ranked(chunks),
        retrieval_ms=10,
        rerank_ms=5,
        retrieval_precision=0.75,
        cache_hit=False,
    )
    assert response.answer_markdown
    assert response.citations
    assert response.citations[0].chunk_id == "c0"
    assert response.faithfulness_score >= 0.0
    assert response.trace.cache_hit is False


@pytest.mark.asyncio
async def test_synthesizer_repairs_unknown_chunk_id(settings: Settings) -> None:
    bad_then_good = [
        SynthesisOutput(
            answer_markdown="Hallucinated answer.",
            claims=[Claim(text="Hallucinated answer.", chunk_ids=["NOT-REAL"])],
        ),
        SynthesisOutput(
            answer_markdown="Repaired answer using real chunk.",
            claims=[
                Claim(
                    text="Repaired answer using real chunk.",
                    chunk_ids=["c0"],
                )
            ],
        ),
    ]

    class StubProvider:
        def __init__(self) -> None:
            self.calls = 0

        async def synthesize(
            self, system: str, user: str, *, max_tokens: int = 2048
        ) -> tuple[SynthesisOutput, int, int]:
            output = bad_then_good[self.calls]
            self.calls += 1
            return output, 100, 50

        async def aclose(self) -> None:
            return None

    provider = StubProvider()
    chunks = [make_mock_chunk("c0", "doc", "Real chunk text about Anthropic.")]
    synthesizer = Synthesizer(settings=settings, provider=provider)
    response = await synthesizer.answer(
        question="Who builds Claude?",
        ranked_chunks=_ranked(chunks),
        retrieval_ms=10,
        rerank_ms=5,
        retrieval_precision=0.75,
        cache_hit=False,
    )
    assert provider.calls == 2
    assert "Repaired" in response.answer_markdown
    assert response.citations[0].chunk_id == "c0"


@pytest.mark.asyncio
async def test_synthesizer_refuses_after_two_failures(settings: Settings) -> None:
    bad = SynthesisOutput(
        answer_markdown="Bad.",
        claims=[Claim(text="Bad.", chunk_ids=["NOT-REAL"])],
    )

    class AlwaysBad:
        async def synthesize(
            self, system: str, user: str, *, max_tokens: int = 2048
        ) -> tuple[SynthesisOutput, int, int]:
            return bad, 100, 50

        async def aclose(self) -> None:
            return None

    chunks = [make_mock_chunk("c0", "doc", "Some text about Anthropic.")]
    synthesizer = Synthesizer(settings=settings, provider=AlwaysBad())
    response = await synthesizer.answer(
        question="Who builds Claude?",
        ranked_chunks=_ranked(chunks),
        retrieval_ms=10,
        rerank_ms=5,
        retrieval_precision=0.75,
        cache_hit=False,
    )
    assert response.faithfulness_score == 0.0
    assert "could not produce" in response.answer_markdown.lower()


@pytest.mark.asyncio
async def test_synthesizer_empty_chunks_returns_empty_response(settings: Settings) -> None:
    synthesizer = Synthesizer(settings=settings, provider=MockSynthesisProvider())
    response = await synthesizer.answer(
        question="Anything?",
        ranked_chunks=[],
        retrieval_ms=2,
        rerank_ms=0,
        retrieval_precision=0.0,
        cache_hit=False,
    )
    assert response.citations == []
    assert response.faithfulness_score == 0.0
