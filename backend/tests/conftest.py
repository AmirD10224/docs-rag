"""Shared pytest fixtures.

Every test runs against `MOCK_PROVIDERS=true`. Integration tests that
need to assert real wire formats (Jina/Cohere/Anthropic) replay VCR
cassettes from `tests/cassettes/`, see `tests/integration/`.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from docs_rag.config import Settings
from docs_rag.deps import Container, build_container
from docs_rag.main import create_app


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def settings() -> Settings:
    return Settings(
        anthropic_api_key=SecretStr("test"),
        cohere_api_key=SecretStr("test"),
        jina_api_key=SecretStr("test"),
        qdrant_url="http://localhost:6333",
        qdrant_api_key=SecretStr(""),
        redis_url="",
        app_env="test",
        log_level="WARNING",
        mock_providers=True,
        embedding_dimensions=64,
        retrieval_top_k_dense=10,
        retrieval_top_k_bm25=10,
        rerank_top_k=4,
        query_cache_ttl_seconds=10,
    )


@pytest_asyncio.fixture
async def container(settings: Settings) -> AsyncIterator[Container]:
    ct = build_container(settings)
    try:
        yield ct
    finally:
        await ct.aclose()


@pytest_asyncio.fixture
async def app(settings: Settings, container: Container) -> AsyncIterator[FastAPI]:
    application = create_app(settings=settings, container=container)
    async with application.router.lifespan_context(application):
        yield application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
