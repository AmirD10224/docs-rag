"""Pydantic v2 strict schemas for ingest, retrieval, synthesis, and citations.

Every external boundary (HTTP, LLM JSON output, vector store record) is
validated through one of these models. The synthesis output schema is the
moat: it forces every claim to carry a `chunk_ids` reference that the
citation enforcer checks before we ever render an answer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class ChunkSpan(StrictModel):
    """Byte-offset span pointing back into the source document."""

    page: int = Field(ge=1, description="1-indexed page number")
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)


class Chunk(StrictModel):
    """A single late-chunked passage with its source span and embedding metadata."""

    chunk_id: NonEmptyStr
    document_id: NonEmptyStr
    text: NonEmptyStr
    span: ChunkSpan
    section_path: list[str] = Field(default_factory=list)
    token_count: int = Field(ge=1)
    created_at: datetime


class IngestRequest(StrictModel):
    source_kind: Literal["pdf_upload", "url"]
    url: str | None = None
    title: NonEmptyStr | None = None


class IngestResponse(StrictModel):
    document_id: NonEmptyStr
    title: NonEmptyStr
    chunk_count: int = Field(ge=0)
    pages: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)


class QueryRequest(StrictModel):
    question: NonEmptyStr = Field(max_length=2000)
    document_ids: list[NonEmptyStr] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


class Citation(StrictModel):
    chunk_id: NonEmptyStr
    document_id: NonEmptyStr
    page: int = Field(ge=1)
    snippet: NonEmptyStr


class Claim(StrictModel):
    """One atomic factual claim extracted from the synthesized answer.

    Claude is required to emit one Claim per sentence, each tagged with the
    chunk_ids it was grounded on. This is what `citation_enforcer` validates.
    """

    text: NonEmptyStr
    chunk_ids: list[NonEmptyStr] = Field(min_length=1)


class SynthesisOutput(StrictModel):
    """The literal JSON shape Claude must emit for /query."""

    answer_markdown: NonEmptyStr
    claims: list[Claim] = Field(min_length=1)
    refused: bool = False
    refusal_reason: str | None = None


class QueryTrace(StrictModel):
    retrieval_ms: int = Field(ge=0)
    rerank_ms: int = Field(ge=0)
    synthesis_ms: int = Field(ge=0)
    total_ms: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    cache_hit: bool


class QueryResponse(StrictModel):
    question: NonEmptyStr
    answer_markdown: NonEmptyStr
    citations: list[Citation]
    claims: list[Claim]
    faithfulness_score: float = Field(ge=0.0, le=1.0)
    retrieval_precision: float = Field(ge=0.0, le=1.0)
    trace: QueryTrace


class CitationLookup(StrictModel):
    chunk_id: NonEmptyStr
    document_id: NonEmptyStr
    text: NonEmptyStr
    span: ChunkSpan
    section_path: list[str]


class EvalScore(StrictModel):
    metric: NonEmptyStr
    value: float = Field(ge=0.0, le=1.0)
    n: int = Field(ge=0)


class DifficultyBreakdown(StrictModel):
    mean_faithfulness: float = Field(ge=0.0, le=1.0)
    n: int = Field(ge=0)


class EvalReport(StrictModel):
    run_id: UUID
    git_sha: str
    created_at: datetime
    prompt_version: str = ""
    synthesis_model: str = ""
    judge_model: str = ""
    mock_providers: bool = False
    scores: list[EvalScore]
    by_difficulty: dict[str, DifficultyBreakdown] = Field(default_factory=dict)
    golden_set_size: int = Field(ge=0)
    duration_seconds: float = Field(ge=0.0)
    cost_usd: float = Field(ge=0.0)
