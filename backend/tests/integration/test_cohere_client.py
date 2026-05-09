from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import SecretStr

from docs_rag.config import Settings
from docs_rag.providers.cohere import CohereError, CohereRerankClient


@pytest.fixture
def cohere_settings() -> Settings:
    return Settings(cohere_api_key=SecretStr("test"), rerank_model="rerank-v3.5")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rerank_returns_index_score_pairs(cohere_settings: Settings) -> None:
    body = {
        "id": "abc",
        "results": [
            {"index": 2, "relevance_score": 0.92},
            {"index": 0, "relevance_score": 0.61},
        ],
    }
    with respx.mock() as router:
        router.post("https://api.cohere.com/v2/rerank").mock(
            return_value=httpx.Response(200, json=body)
        )
        async with httpx.AsyncClient() as http:
            client = CohereRerankClient(cohere_settings, http_client=http)
            results = await client.rerank("q", ["doc-a", "doc-b", "doc-c"], top_k=2)
    assert results == [(2, 0.92), (0, 0.61)]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rerank_empty_inputs(cohere_settings: Settings) -> None:
    async with httpx.AsyncClient() as http:
        client = CohereRerankClient(cohere_settings, http_client=http)
        assert await client.rerank("q", [], top_k=5) == []
        assert await client.rerank("q", ["a"], top_k=0) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rerank_4xx(cohere_settings: Settings) -> None:
    with respx.mock() as router:
        router.post("https://api.cohere.com/v2/rerank").mock(
            return_value=httpx.Response(400, text="nope")
        )
        async with httpx.AsyncClient() as http:
            client = CohereRerankClient(cohere_settings, http_client=http)
            with pytest.raises(CohereError):
                await client.rerank("q", ["doc"], top_k=1)
