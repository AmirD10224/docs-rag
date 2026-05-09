"""Redis-backed cache with a deterministic in-memory fallback for tests.

We cache two things:
  1. Query → answer (TTL = settings.query_cache_ttl_seconds)
  2, content-hash → embedding (no TTL; embeddings are deterministic for a
     given text + model)

The fallback `InMemoryCache` is used when REDIS_URL is unreachable or in
unit tests. Behavior is identical for our purposes (TTL respected, no
cross-process sharing).
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Protocol

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

_log = structlog.get_logger(__name__)


def _normalize_str(value: str) -> str:
    """Normalize a query string so trivial variants share a cache key.

    Whitespace, case, and unicode width are not semantic differences; folding
    them defeats the most obvious cache-bypass attacks (appending a counter
    suffix, switching case, inserting zero-width spaces).
    """
    import unicodedata

    folded = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(folded.split())


def stable_key(*parts: object) -> str:
    """Hash a tuple of parts into a stable, normalization-aware cache key.

    Strings are NFKC-normalized + lowercased + whitespace-collapsed before
    hashing. Non-string parts are JSON-encoded as-is.
    """
    normalized: list[object] = [_normalize_str(p) if isinstance(p, str) else p for p in parts]
    payload = json.dumps(normalized, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class Cache(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def aclose(self) -> None: ...


class InMemoryCache:
    """Process-local cache used in tests and as a graceful Redis fallback."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float | None]] = {}

    async def get(self, key: str) -> str | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and expires_at < time.time():
            self._data.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        self._data[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def aclose(self) -> None:
        self._data.clear()


class RedisCache:
    def __init__(self, client: Redis) -> None:
        self._client = client

    @classmethod
    def from_url(cls, url: str, *, socket_timeout: float = 5.0) -> RedisCache:
        return cls(
            Redis.from_url(
                url,
                decode_responses=True,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_timeout,
            )
        )

    async def get(self, key: str) -> str | None:
        try:
            result = await self._client.get(key)
        except RedisError as exc:
            _log.warning("cache.get.error", key=key, error=str(exc))
            return None
        return result if isinstance(result, str) else None

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        try:
            if ttl_seconds and ttl_seconds > 0:
                await self._client.setex(key, ttl_seconds, value)
            else:
                await self._client.set(key, value)
        except RedisError as exc:
            _log.warning("cache.set.error", key=key, error=str(exc))

    async def delete(self, key: str) -> None:
        try:
            await self._client.delete(key)
        except RedisError as exc:
            _log.warning("cache.delete.error", key=key, error=str(exc))

    async def aclose(self) -> None:
        await self._client.aclose()
