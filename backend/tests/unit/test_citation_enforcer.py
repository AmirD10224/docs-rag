from __future__ import annotations

import pytest

from docs_rag.providers.mocks import make_mock_chunk
from docs_rag.synthesis.citation_enforcer import CitationViolation, enforce
from docs_rag.synthesis.schema import Claim, SynthesisOutput


def test_valid_citations_pass() -> None:
    chunks = [
        make_mock_chunk("a", "d1", "Claude is built by Anthropic and excels at reasoning."),
        make_mock_chunk("b", "d1", "Bicycles are vehicles with two wheels."),
    ]
    output = SynthesisOutput(
        answer_markdown="Claude is built by Anthropic and is good at reasoning.",
        claims=[
            Claim(
                text="Claude is built by Anthropic and is good at reasoning.",
                chunk_ids=["a"],
            )
        ],
        refused=False,
    )
    result = enforce(output, chunks)
    assert 0.0 <= result.faithfulness_score <= 1.0
    assert result.faithfulness_score > 0.0


def test_unknown_chunk_id_raises() -> None:
    chunks = [make_mock_chunk("a", "d1", "Real chunk text.")]
    output = SynthesisOutput(
        answer_markdown="Hallucinated.",
        claims=[Claim(text="Hallucinated.", chunk_ids=["NOT-REAL"])],
        refused=False,
    )
    with pytest.raises(CitationViolation):
        enforce(output, chunks)


def test_no_chunks_raises() -> None:
    output = SynthesisOutput(
        answer_markdown="x",
        claims=[Claim(text="x", chunk_ids=["a"])],
    )
    with pytest.raises(CitationViolation):
        enforce(output, [])


def test_low_overlap_lowers_faithfulness() -> None:
    chunks = [make_mock_chunk("a", "d1", "Quantum mechanics describes subatomic particles.")]
    output = SynthesisOutput(
        answer_markdown="Bicycles are popular in Amsterdam.",
        claims=[Claim(text="Bicycles are popular in Amsterdam.", chunk_ids=["a"])],
    )
    result = enforce(output, chunks)
    assert result.faithfulness_score == 0.0
