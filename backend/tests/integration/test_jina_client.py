"""Live-format test for the Jina embeddings client.

We use respx (not VCR) because the Jina client uses a directly-injected
httpx.AsyncClient, which respx intercepts cleanly and produces
deterministic test fixtures we can edit by hand without re-recording.

The asserted shape mirrors Jina's v1 embeddings response. If Jina
changes the wire format, this test fails immediately rather than
waiting for prod traffic to surface the regression.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from docs_rag.config import Settings
from docs_rag.providers.jina import JinaEmbeddingClient


@pytest.fixture
def jina_settings() -> Settings:
    from pydantic import SecretStr

    return Settings(
        jina_api_key=SecretStr("test"),
        embedding_model="jina-embeddings-v3",
        embedding_dimensions=64,
    )


def _vec(seed: int, dim: int = 64) -> list[float]:
    """Return a length-dim vector seeded by `seed` (deterministic)."""
    return [round(((seed * 7 + i * 3) % 17) / 17.0, 4) for i in range(dim)]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_embed_query_parses_response(jina_settings: Settings) -> None:
    expected = _vec(1)
    body = {
        "data": [{"embedding": expected, "index": 0}],
        "usage": {"total_tokens": 7},
    }
    with respx.mock() as router:
        router.post("https://api.jina.ai/v1/embeddings").mock(
            return_value=httpx.Response(200, json=body)
        )
        async with httpx.AsyncClient() as http:
            client = JinaEmbeddingClient(jina_settings, http_client=http)
            vec = await client.embed_query("hello")
    assert vec == expected


@pytest.mark.integration
@pytest.mark.asyncio
async def test_embed_chunks_late_returns_one_vector_per_span(jina_settings: Settings) -> None:
    body = {
        "data": [
            {"embedding": _vec(1), "index": 0},
            {"embedding": _vec(2), "index": 1},
        ],
        "usage": {"total_tokens": 14},
    }
    with respx.mock() as router:
        route = router.post("https://api.jina.ai/v1/embeddings").mock(
            return_value=httpx.Response(200, json=body)
        )
        async with httpx.AsyncClient() as http:
            client = JinaEmbeddingClient(jina_settings, http_client=http)
            vectors, tokens = await client.embed_chunks_late("abcdefghij", [(0, 5), (5, 10)])
    assert tokens == 14
    assert len(vectors) == 2
    request = route.calls[0].request
    payload = request.read().decode("utf-8")
    assert '"late_chunking": true' in payload or '"late_chunking":true' in payload
    assert '"chunk_spans"' in payload


@pytest.mark.integration
@pytest.mark.asyncio
async def test_jina_4xx_raises(jina_settings: Settings) -> None:
    from docs_rag.providers.jina import JinaError

    with respx.mock() as router:
        router.post("https://api.jina.ai/v1/embeddings").mock(
            return_value=httpx.Response(400, text="bad request")
        )
        async with httpx.AsyncClient() as http:
            client = JinaEmbeddingClient(jina_settings, http_client=http)
            with pytest.raises(JinaError):
                await client.embed_query("hello")
