"""Unit tests for the SSRF allowlist + URL-fetch safety helpers.

These exercise the boundary that protects /ingest from being used as a
proxy to internal cloud-metadata endpoints. They are unit tests (no
network) because we monkeypatch `socket.getaddrinfo` and the httpx
client.
"""

from __future__ import annotations

import socket
from typing import Any

import httpx
import pytest
import respx

from docs_rag.observability.security import (
    UnsafeURLError,
    _is_blocked_ip,
    assert_url_is_safe,
    looks_like_pdf_bytes,
    safe_fetch_bytes,
)


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "::1",
        "10.0.0.1",
        "192.168.1.1",
        "172.16.0.1",
        "169.254.169.254",  # AWS/GCE metadata
        "0.0.0.0",
        "224.0.0.1",  # multicast
    ],
)
def test_is_blocked_ip_blocks_dangerous_ranges(ip: str) -> None:
    assert _is_blocked_ip(ip) is True


@pytest.mark.parametrize("ip", ["8.8.8.8", "1.1.1.1", "151.101.1.69"])
def test_is_blocked_ip_allows_public_addresses(ip: str) -> None:
    assert _is_blocked_ip(ip) is False


def test_is_blocked_ip_refuses_unparseable() -> None:
    assert _is_blocked_ip("not-an-ip") is True


def test_assert_url_is_safe_blocks_non_http_scheme() -> None:
    with pytest.raises(UnsafeURLError, match="scheme"):
        assert_url_is_safe("file:///etc/passwd")


def test_assert_url_is_safe_blocks_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(UnsafeURLError, match="blocked"):
        assert_url_is_safe("http://localhost/x")


def test_assert_url_is_safe_blocks_metadata_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(UnsafeURLError, match="blocked"):
        assert_url_is_safe("http://metadata.google.internal/x")


def test_assert_url_is_safe_blocks_private_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_resolve(host: str, _port: int) -> list[Any]:
        return [(socket.AF_INET, None, None, "", ("10.0.0.1", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_resolve)
    with pytest.raises(UnsafeURLError, match="blocked address"):
        assert_url_is_safe("http://attacker.example.com/x")


def test_assert_url_is_safe_passes_for_public(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_resolve(host: str, _port: int) -> list[Any]:
        return [(socket.AF_INET, None, None, "", ("151.101.1.69", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_resolve)
    assert_url_is_safe("https://example.com/")


def test_looks_like_pdf_bytes_accepts_pdf() -> None:
    assert looks_like_pdf_bytes(b"%PDF-1.4\nrest") is True


def test_looks_like_pdf_bytes_rejects_html() -> None:
    assert looks_like_pdf_bytes(b"<!doctype html>") is False


@pytest.mark.asyncio
async def test_safe_fetch_caps_response_size(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_resolve(host: str, _port: int) -> list[Any]:
        return [(socket.AF_INET, None, None, "", ("151.101.1.69", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_resolve)

    with respx.mock() as router:
        router.get("https://example.com/big").mock(
            return_value=httpx.Response(200, content=b"x" * 1024)
        )
        with pytest.raises(UnsafeURLError, match="exceeded max_bytes"):
            await safe_fetch_bytes(
                "https://example.com/big",
                max_bytes=128,
                timeout_seconds=5.0,
            )


@pytest.mark.asyncio
async def test_safe_fetch_returns_body_and_content_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_resolve(host: str, _port: int) -> list[Any]:
        return [(socket.AF_INET, None, None, "", ("151.101.1.69", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_resolve)

    with respx.mock() as router:
        router.get("https://example.com/ok").mock(
            return_value=httpx.Response(
                200, content=b"hello", headers={"content-type": "text/plain"}
            )
        )
        body, ct = await safe_fetch_bytes(
            "https://example.com/ok", max_bytes=1024, timeout_seconds=5.0
        )
    assert body == b"hello"
    assert ct == "text/plain"
