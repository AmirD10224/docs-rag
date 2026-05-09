from __future__ import annotations

import asyncio

import pytest

from docs_rag.observability.cache import InMemoryCache, stable_key


@pytest.mark.asyncio
async def test_set_and_get() -> None:
    cache = InMemoryCache()
    await cache.set("k", "v")
    assert await cache.get("k") == "v"


@pytest.mark.asyncio
async def test_ttl_expiry() -> None:
    cache = InMemoryCache()
    await cache.set("k", "v", ttl_seconds=1)
    await asyncio.sleep(1.05)
    assert await cache.get("k") is None


@pytest.mark.asyncio
async def test_delete() -> None:
    cache = InMemoryCache()
    await cache.set("k", "v")
    await cache.delete("k")
    assert await cache.get("k") is None


def test_stable_key_is_deterministic() -> None:
    a = stable_key("query", ["doc1", "doc2"], 5)
    b = stable_key("query", ["doc1", "doc2"], 5)
    assert a == b


def test_stable_key_changes_with_inputs() -> None:
    a = stable_key("query", ["doc1"], 5)
    b = stable_key("query", ["doc2"], 5)
    assert a != b
