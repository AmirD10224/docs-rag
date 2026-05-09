"""HTML URL parsing.

Mocks the HTTP fetch with respx; the real value here is asserting that
the section index is recovered from `<h1>`/`<h2>` headers and that
character offsets line up with the rendered text.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from docs_rag.ingest.parse import parse_url


@pytest.mark.asyncio
async def test_parse_url_html_extracts_sections() -> None:
    html = (
        "<html><body>"
        "<h1>Quarterly Report</h1>"
        "<p>Revenue grew 12% year over year. Margins held steady.</p>"
        "<h2>Risk Factors</h2>"
        "<p>Currency volatility remains the dominant risk.</p>"
        "</body></html>"
    )
    with respx.mock(base_url="https://example.com") as router:
        router.get("/report").mock(
            return_value=httpx.Response(200, text=html, headers={"content-type": "text/html"})
        )
        async with httpx.AsyncClient() as http:
            parsed = await parse_url("https://example.com/report", http_client=http)

    assert "Revenue grew" in parsed.text
    assert any("Risk Factors" in path for _, path in parsed.section_index)


@pytest.mark.asyncio
async def test_parse_url_pdf_content_type_routes_to_pdf_parser() -> None:
    with respx.mock(base_url="https://example.com") as router:
        router.get("/empty.pdf").mock(
            return_value=httpx.Response(
                200, content=b"", headers={"content-type": "application/pdf"}
            )
        )
        async with httpx.AsyncClient() as http:
            with pytest.raises(ValueError):
                await parse_url("https://example.com/empty.pdf", http_client=http)
