"""GET /citation/{chunk_id}, fetch source span for inline highlight."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, HTTPException, Request, status

from docs_rag.deps import Container
from docs_rag.synthesis.schema import CitationLookup

router = APIRouter(prefix="/citation", tags=["citation"])


@router.get("/{chunk_id}", response_model=CitationLookup)
async def get_citation(chunk_id: str, request: Request) -> CitationLookup:
    container = cast(Container, request.app.state.container)
    chunk = await container.vector_store.get_chunk(chunk_id)
    if chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"chunk {chunk_id} not found",
        )
    return CitationLookup(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        text=chunk.text,
        span=chunk.span,
        section_path=list(chunk.section_path),
    )
