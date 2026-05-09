"""POST /ingest, accepts a PDF upload OR a URL, returns IngestResponse.

Defenses applied here (see docs_rag/observability/security.py for the
shared helpers):

  - Per-IP rate limit (slowapi, see main.py)
  - Optional Bearer auth (when AUTH_BEARER_TOKEN is set)
  - SSRF-safe URL fetcher (`safe_fetch_bytes`)
  - Streaming size cap on PDF uploads, we read in chunks and reject
    before fully buffering anything large
  - Magic-byte sniff: any uploaded file must start with `%PDF-`
  - Daily cost cap circuit breaker (CostGuard) for the cost-driving paths
"""

from __future__ import annotations

from typing import Annotated, Final, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import HttpUrl, ValidationError

from docs_rag.deps import Container
from docs_rag.observability.cost_guard import CostCapExceeded
from docs_rag.observability.security import (
    UnsafeURLError,
    auth_required,
    looks_like_pdf_bytes,
)
from docs_rag.observability.tracing import request_scope
from docs_rag.synthesis.schema import IngestResponse

router = APIRouter(prefix="/ingest", tags=["ingest"])

_CHUNK_SIZE: Final = 64 * 1024


async def _read_with_cap(file: UploadFile, max_bytes: int) -> bytes:
    """Read the upload in chunks, rejecting before we buffer >max_bytes.

    `UploadFile.read()` would happily slurp the entire body into memory -
    a 5GB upload OOMs the 1GB Fly VM. We stream and abort early.
    """
    buf = bytearray()
    while True:
        chunk = await file.read(_CHUNK_SIZE)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"upload exceeds {max_bytes // (1024 * 1024)}MB limit",
            )
    return bytes(buf)


def _make_dependency(request: Request) -> object:
    """Late-bind the auth dep so it can read settings from app.state."""
    container = cast(Container, request.app.state.container)
    return auth_required(container.settings)


@router.post(
    "",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a PDF or URL",
)
async def ingest(
    request: Request,
    _auth: Annotated[None, Depends(_make_dependency)] = None,
    file: Annotated[UploadFile | None, File()] = None,
    url: Annotated[str | None, Form()] = None,
    title: Annotated[str | None, Form()] = None,
) -> IngestResponse:
    if (file is None) == (url is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="provide exactly one of `file` or `url`",
        )

    container = cast(Container, request.app.state.container)
    settings = container.settings

    with request_scope() as _trace:
        if file is not None:
            data = await _read_with_cap(file, settings.max_pdf_mb * 1024 * 1024)
            if not data:
                raise HTTPException(400, "empty upload")
            if not looks_like_pdf_bytes(data):
                raise HTTPException(415, "uploaded file is not a PDF (missing %PDF- header)")
            try:
                return await container.pipeline.ingest_pdf_bytes(data, title=title or file.filename)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            except CostCapExceeded as exc:
                raise HTTPException(429, str(exc)) from exc

        try:
            HttpUrl(url)  # type: ignore[arg-type]
        except ValidationError as exc:
            raise HTTPException(400, "invalid url") from exc

        try:
            assert url is not None
            return await container.pipeline.ingest_url(url)
        except UnsafeURLError as exc:
            raise HTTPException(400, f"unsafe url: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except CostCapExceeded as exc:
            raise HTTPException(429, str(exc)) from exc
