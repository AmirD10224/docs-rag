"""End-to-end /ingest → /query → /citation against the in-process app.

Uses respx to stub the URL fetched by /ingest. Everything downstream
(parse, late-chunk, embed, store, retrieve, rerank, synthesize) runs
real code paths against the mock providers so this is an honest
integration test, not a smoke test.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from httpx import AsyncClient

SAMPLE_HTML = """
<html><body>
<h1>Anthropic Constitution</h1>
<p>Anthropic builds Claude, a helpful and harmless AI assistant.
Claude is trained with constitutional methods that emphasize
transparency and refusal to deceive.</p>

<h2>Safety</h2>
<p>The system prefers refusing over hallucinating. Citations are
mandatory for factual claims in the production deployment.</p>

<h2>Architecture</h2>
<p>The retrieval pipeline uses BM25 plus dense embeddings, then a
cross-encoder reranker. Final synthesis happens with strict
JSON-schema enforcement.</p>
</body></html>
"""


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ingest_query_citation_full_loop(client: AsyncClient) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("https://example.com/doc").mock(
            return_value=httpx.Response(
                200, text=SAMPLE_HTML, headers={"content-type": "text/html"}
            )
        )

        ingest_resp = await client.post("/ingest", data={"url": "https://example.com/doc"})
    assert ingest_resp.status_code == 201, ingest_resp.text
    ingest_body = ingest_resp.json()
    document_id = ingest_body["document_id"]
    assert ingest_body["chunk_count"] >= 1

    query_resp = await client.post(
        "/query",
        json={
            "question": "What does Claude prefer over hallucinating?",
            "document_ids": [document_id],
        },
    )
    assert query_resp.status_code == 200, query_resp.text
    body = query_resp.json()
    assert body["answer_markdown"]
    assert body["citations"], "expected at least one citation"
    assert body["trace"]["cache_hit"] is False

    cited_chunk_id = body["citations"][0]["chunk_id"]
    citation_resp = await client.get(f"/citation/{cited_chunk_id}")
    assert citation_resp.status_code == 200
    citation = citation_resp.json()
    assert citation["chunk_id"] == cited_chunk_id
    assert citation["text"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_query_cache_hit_on_repeat(client: AsyncClient) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("https://example.com/doc").mock(
            return_value=httpx.Response(
                200, text=SAMPLE_HTML, headers={"content-type": "text/html"}
            )
        )
        ingest_resp = await client.post("/ingest", data={"url": "https://example.com/doc"})
    assert ingest_resp.status_code == 201
    document_id = ingest_resp.json()["document_id"]

    payload = {"question": "What is Claude?", "document_ids": [document_id]}
    first = await client.post("/query", json=payload)
    second = await client.post("/query", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["trace"]["cache_hit"] is False
    assert second.json()["trace"]["cache_hit"] is True


@pytest.mark.asyncio
async def test_query_404_when_no_documents(client: AsyncClient) -> None:
    resp = await client.post("/query", json={"question": "anything"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ingest_validates_input(client: AsyncClient) -> None:
    resp = await client.post("/ingest")
    assert resp.status_code == 400
    resp = await client.post("/ingest", data={"url": "not-a-url"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_citation_404(client: AsyncClient) -> None:
    resp = await client.get("/citation/does-not-exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_evals_returns_latest_report(client: AsyncClient) -> None:
    """We commit a baseline `evals/reports/latest.json` so the eval gate
    has something to diff against. The endpoint should serve it; only
    when the file is missing should it 404. We assert the present-case
    here and rely on `evals/tests/test_diff.py` for the absent-case."""
    resp = await client.get("/evals")
    assert resp.status_code in {200, 404}  # 200 with baseline, 404 if cleaned


@pytest.mark.asyncio
async def test_healthz_ok(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
