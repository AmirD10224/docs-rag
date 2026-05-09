"""Late-chunking span planner."""

from __future__ import annotations

from itertools import pairwise

from docs_rag.ingest.chunk import (
    content_hash,
    make_document_id,
    materialize,
    plan_chunks,
)
from docs_rag.ingest.parse import PageOffset, ParsedDocument


def _make_doc(text: str) -> ParsedDocument:
    return ParsedDocument(
        title="t",
        text=text,
        page_offsets=[PageOffset(page=1, char_start=0, char_end=len(text))],
        section_index=[(0, ["Intro"])],
    )


def test_short_document_yields_at_least_one_chunk() -> None:
    text = "Anthropic builds Claude. " * 20
    parsed = _make_doc(text)
    plans = plan_chunks("docX", parsed)

    assert plans, "expected at least one chunk plan"
    for plan in plans:
        assert plan.text
        assert plan.span.char_end > plan.span.char_start
        assert plan.span.char_end <= len(parsed.text)
        assert plan.section_path == ["Intro"]


def test_long_paragraph_is_split() -> None:
    sentence = "This is sentence number {n} with sufficient padding text to grow. "
    paragraph = "".join(sentence.format(n=i) for i in range(120))
    parsed = _make_doc(paragraph)
    plans = plan_chunks("docY", parsed)

    assert len(plans) >= 2
    # Adjacent chunk overlap (late-chunking continuity). Use itertools.pairwise
    # to walk the consecutive (a, b) pairs without an off-by-one zip.
    spans = [(p.span.char_start, p.span.char_end) for p in plans]
    overlaps = [b_start < a_end for (_, a_end), (b_start, _) in pairwise(spans)]
    assert any(overlaps)


def test_multi_paragraph_chunks_are_unique() -> None:
    text = "\n\n".join(f"Paragraph {i}. " * 40 for i in range(8))
    parsed = _make_doc(text)
    plans = plan_chunks("docZ", parsed)
    chunk_ids = [p.chunk_id for p in plans]
    assert len(chunk_ids) == len(set(chunk_ids))


def test_materialize_round_trips_metadata() -> None:
    parsed = _make_doc("Some text. " * 50)
    plans = plan_chunks("docM", parsed)
    chunks = materialize(plans, "docM")
    assert len(chunks) == len(plans)
    for plan, chunk in zip(plans, chunks, strict=True):
        assert chunk.chunk_id == plan.chunk_id
        assert chunk.text == plan.text
        assert chunk.token_count == plan.token_count


def test_document_id_stable_for_same_inputs() -> None:
    h = content_hash(b"hello")
    assert make_document_id("title", h) == make_document_id("title", h)


def test_document_id_changes_with_content() -> None:
    h1 = content_hash(b"hello")
    h2 = content_hash(b"world")
    assert make_document_id("title", h1) != make_document_id("title", h2)
