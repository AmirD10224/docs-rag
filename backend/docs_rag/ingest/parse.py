"""PDF and URL parsing.

Pipeline:
  1. PDF bytes → pdfplumber pages → page-aware text with character offsets.
  2, unstructured `partition` (or `partition_html` for URL) → element list,
     used to recover the heading hierarchy (`section_path`) for each chunk.
  3. Returned `ParsedDocument` carries the full normalized text and per-page
     character offset map so chunkers can produce citation-grade spans.

We don't OCR scanned PDFs in v0.1, pdfplumber returns empty text and the
caller surfaces a 422. This is documented in ARCHITECTURE.md.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import httpx
import pdfplumber
import structlog

_log = structlog.get_logger(__name__)
_HEADING_RE = re.compile(r"^(#+\s+|[A-Z][A-Z0-9 \-]{4,})$")


@dataclass(slots=True)
class PageOffset:
    page: int
    char_start: int
    char_end: int


@dataclass(slots=True)
class ParsedDocument:
    title: str
    text: str
    page_offsets: list[PageOffset]
    section_index: list[tuple[int, list[str]]] = field(default_factory=list)
    """Sorted (char_offset, section_path), section_path active from that offset on."""

    @property
    def page_count(self) -> int:
        return len(self.page_offsets)

    def page_for_offset(self, offset: int) -> int:
        for page in self.page_offsets:
            if page.char_start <= offset < page.char_end:
                return page.page
        return self.page_offsets[-1].page if self.page_offsets else 1

    def section_for_offset(self, offset: int) -> list[str]:
        active: list[str] = []
        for boundary, section_path in self.section_index:
            if boundary <= offset:
                active = section_path
            else:
                break
        return active


async def parse_pdf_bytes(data: bytes, *, title: str | None = None) -> ParsedDocument:
    if not data:
        raise ValueError("empty pdf bytes")
    parts: list[str] = []
    page_offsets: list[PageOffset] = []
    section_index: list[tuple[int, list[str]]] = []
    section_stack: list[str] = []
    cursor = 0
    derived_title = title

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            for line in page_text.splitlines():
                stripped = line.strip()
                if _looks_like_heading(stripped):
                    if section_stack and len(stripped) > len(section_stack[-1]):
                        section_stack[-1] = stripped
                    else:
                        section_stack.append(stripped)
                        if len(section_stack) > 4:
                            section_stack = section_stack[-4:]
                    section_index.append((cursor, list(section_stack)))
            if i == 1 and not derived_title:
                derived_title = _first_nonempty(page_text) or "Untitled document"

            block = page_text + "\n\n"
            page_offsets.append(PageOffset(page=i, char_start=cursor, char_end=cursor + len(block)))
            parts.append(block)
            cursor += len(block)

    text = "".join(parts).rstrip()
    if not text:
        raise ValueError("pdf produced no extractable text (scanned image?)")

    return ParsedDocument(
        title=(derived_title or "Untitled document").strip()[:200],
        text=text,
        page_offsets=page_offsets,
        section_index=section_index,
    )


async def parse_url(
    url: str,
    *,
    http_client: httpx.AsyncClient | None = None,
    max_bytes: int = 25 * 1024 * 1024,
    timeout_seconds: float = 15.0,
) -> ParsedDocument:
    """Fetch and parse a URL.

    Defends against:
      - SSRF: hostname/IP allowlist via `assert_url_is_safe` (blocks
        loopback, link-local, RFC1918, cloud-metadata addresses).
      - Memory exhaustion: streaming with a hard `max_bytes` cap.
      - Redirect SSRF: each hop is re-validated; we do not pass
        `follow_redirects=True` to httpx because that would skip the check.
    """
    from docs_rag.observability.security import safe_fetch_bytes

    body, content_type = await safe_fetch_bytes(
        url,
        max_bytes=max_bytes,
        timeout_seconds=timeout_seconds,
        http_client=http_client,
    )
    if "pdf" in content_type.lower() or url.lower().endswith(".pdf"):
        return await parse_pdf_bytes(body, title=_filename(url))
    return _parse_html(body.decode("utf-8", errors="replace"), title=_filename(url))


def _parse_html(html: str, *, title: str) -> ParsedDocument:
    from unstructured.partition.html import partition_html

    elements = partition_html(text=html)
    parts: list[str] = []
    section_index: list[tuple[int, list[str]]] = []
    section_stack: list[str] = []
    cursor = 0

    for element in elements:
        text = (element.text or "").strip()
        if not text:
            continue
        category = getattr(element, "category", "") or ""
        if category in {"Title", "Header"}:
            section_stack = [*section_stack, text][-4:]
            section_index.append((cursor, list(section_stack)))
        block = text + "\n\n"
        parts.append(block)
        cursor += len(block)

    body = "".join(parts).rstrip()
    if not body:
        raise ValueError("url produced no extractable text")

    derived_title = (
        next(
            (
                getattr(e, "text", "")
                for e in elements
                if getattr(e, "category", "") == "Title" and (e.text or "").strip()
            ),
            title,
        )
        or title
    )

    page_offsets = [PageOffset(page=1, char_start=0, char_end=len(body))]
    return ParsedDocument(
        title=derived_title.strip()[:200],
        text=body,
        page_offsets=page_offsets,
        section_index=section_index,
    )


def _looks_like_heading(line: str) -> bool:
    if not line or len(line) > 120:
        return False
    if _HEADING_RE.match(line):
        return True
    return bool(line.endswith(":") and len(line) <= 80 and line[0].isupper())


def _first_nonempty(text: str) -> str | None:
    for line in text.splitlines():
        candidate = line.strip()
        if candidate:
            return candidate[:200]
    return None


def _filename(url: str) -> str:
    tail = url.rstrip("/").split("/")[-1] or url
    return tail[:200]
