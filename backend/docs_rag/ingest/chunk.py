"""Chunk-span planner.

The actual *embedding* step is "late": Jina v3 encodes the full document
once, then pools per-span. This module's job is to produce the spans -
character offsets that respect sentence/paragraph boundaries and the
target token window. The embedder consumes those spans verbatim.

Chunking strategy:
  - Target ~400 tokens per chunk, ~80 token overlap.
  - Hard splits on paragraph boundaries; soft splits on sentence
    boundaries when a paragraph exceeds the window.
  - Each chunk's `section_path` comes from the parser's section index
    so the synthesizer can show "Item 7. Management's Discussion" etc.

Token counts use a 1-tok ≈ 4-char heuristic (good enough for span
planning; the embedder reports ground-truth token usage for cost).
"""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from docs_rag.ingest.parse import ParsedDocument
from docs_rag.synthesis.schema import Chunk, ChunkSpan

_PARAGRAPH_RE = re.compile(r"\n{2,}")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_TARGET_TOKENS = 400
_OVERLAP_TOKENS = 80
_MIN_TOKENS = 40
_CHARS_PER_TOKEN = 4


@dataclass(slots=True)
class ChunkPlan:
    """The pre-embedding chunk record. Embeddings are attached later."""

    chunk_id: str
    span: ChunkSpan
    text: str
    section_path: list[str]
    token_count: int


def plan_chunks(document_id: str, parsed: ParsedDocument) -> list[ChunkPlan]:
    """Return ordered ChunkPlans covering the document text.

    Spans never cross paragraph boundaries unless a single paragraph is
    larger than the target window, in which case sentence splitting
    kicks in. Adjacent chunks share `_OVERLAP_TOKENS` of context to
    keep retrieval recall high near boundaries.
    """
    spans: list[tuple[int, int]] = []
    paragraph_offsets = _paragraph_offsets(parsed.text)

    target_chars = _TARGET_TOKENS * _CHARS_PER_TOKEN
    overlap_chars = _OVERLAP_TOKENS * _CHARS_PER_TOKEN
    min_chars = _MIN_TOKENS * _CHARS_PER_TOKEN

    buf_start: int | None = None
    buf_end = 0

    for p_start, p_end in paragraph_offsets:
        p_len = p_end - p_start
        if p_len > target_chars:
            if buf_start is not None and buf_end - buf_start >= min_chars:
                spans.append((buf_start, buf_end))
                buf_start = None
            spans.extend(_split_long(parsed.text, p_start, p_end, target_chars, overlap_chars))
            continue

        if buf_start is None:
            buf_start = p_start
            buf_end = p_end
            continue

        if p_end - buf_start <= target_chars:
            buf_end = p_end
            continue

        if buf_end - buf_start >= min_chars:
            spans.append((buf_start, buf_end))
        new_start = max(buf_start, buf_end - overlap_chars)
        buf_start = min(new_start, p_start)
        buf_end = p_end

    if buf_start is not None and buf_end - buf_start >= min_chars:
        spans.append((buf_start, buf_end))

    plans: list[ChunkPlan] = []
    seen: set[tuple[int, int]] = set()
    for index, (start, end) in enumerate(spans):
        if (start, end) in seen:
            continue
        seen.add((start, end))
        text = parsed.text[start:end].strip()
        if len(text) < min_chars:
            continue
        chunk_id = _chunk_id(document_id, index, start, end, text)
        plans.append(
            ChunkPlan(
                chunk_id=chunk_id,
                span=ChunkSpan(
                    page=parsed.page_for_offset(start),
                    char_start=start,
                    char_end=end,
                ),
                text=text,
                section_path=parsed.section_for_offset(start),
                token_count=max(1, math.ceil(len(text) / _CHARS_PER_TOKEN)),
            )
        )
    return plans


def materialize(plans: list[ChunkPlan], document_id: str) -> list[Chunk]:
    now = datetime.now(UTC)
    return [
        Chunk(
            chunk_id=plan.chunk_id,
            document_id=document_id,
            text=plan.text,
            span=plan.span,
            section_path=plan.section_path,
            token_count=plan.token_count,
            created_at=now,
        )
        for plan in plans
    ]


def _paragraph_offsets(text: str) -> list[tuple[int, int]]:
    offsets: list[tuple[int, int]] = []
    start = 0
    for match in _PARAGRAPH_RE.finditer(text):
        end = match.start()
        if end > start and text[start:end].strip():
            offsets.append((start, end))
        start = match.end()
    if start < len(text) and text[start:].strip():
        offsets.append((start, len(text)))
    return offsets


def _split_long(
    text: str, start: int, end: int, target_chars: int, overlap_chars: int
) -> list[tuple[int, int]]:
    body = text[start:end]
    sentence_breaks = [m.end() for m in _SENTENCE_RE.finditer(body)]
    sentence_breaks = [0, *sentence_breaks, len(body)]

    spans: list[tuple[int, int]] = []
    cursor = 0
    while cursor < len(body):
        target = min(cursor + target_chars, len(body))
        cut = max(
            (b for b in sentence_breaks if cursor < b <= target),
            default=target,
        )
        spans.append((start + cursor, start + cut))
        if cut >= len(body):
            break
        cursor = max(cursor, cut - overlap_chars)
    return spans


def _chunk_id(document_id: str, index: int, start: int, end: int, text: str) -> str:
    digest = hashlib.sha1(
        f"{document_id}:{index}:{start}:{end}:{text[:64]}".encode(),
        usedforsecurity=False,
    ).hexdigest()[:12]
    return f"{document_id[:8]}-{index:04d}-{digest}"


def make_document_id(title: str, content_hash: str) -> str:
    seed = f"{title}|{content_hash}".encode()
    return uuid.uuid5(uuid.NAMESPACE_URL, seed.decode("utf-8")).hex


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
