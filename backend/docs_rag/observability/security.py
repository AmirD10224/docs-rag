"""Security helpers: SSRF allowlist, URL fetcher with size cap, auth dependency.

We deliberately keep these in a single module so the threat model lives in one
place. See ARCHITECTURE.md for rationale.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx
import structlog

from docs_rag.config import Settings

_log = structlog.get_logger(__name__)


class UnsafeURLError(ValueError):
    """Raised when a URL points at a private / loopback / link-local target."""


_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "ip6-localhost",
        "ip6-loopback",
        "metadata.google.internal",  # GCE metadata
        "metadata",
    }
)
_ALLOWED_SCHEMES = frozenset({"http", "https"})


def _is_blocked_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # if we can't parse it, refuse
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def assert_url_is_safe(url: str) -> None:
    """Raise UnsafeURLError if the URL points anywhere we shouldn't fetch.

    Defense in depth: block by scheme, by hostname, and by resolved IP.
    Resolution is synchronous (DNS); cheap, runs once per /ingest call.
    """
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise UnsafeURLError(f"scheme {scheme!r} not allowed")
    host = (parsed.hostname or "").lower()
    if not host:
        raise UnsafeURLError("missing host")
    if host in _BLOCKED_HOSTNAMES:
        raise UnsafeURLError(f"host {host!r} is blocked")
    # Resolve every A/AAAA record. If ANY resolves to a private range, refuse -
    # we don't want a public DNS answer that includes 169.254.169.254 to slip
    # through.
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if scheme == "https" else 80))
    except socket.gaierror as exc:
        raise UnsafeURLError(f"could not resolve {host!r}: {exc}") from exc
    for info in infos:
        sockaddr = info[4]
        ip = sockaddr[0]
        if not isinstance(ip, str):
            raise UnsafeURLError(f"unexpected address tuple from getaddrinfo: {sockaddr!r}")
        if _is_blocked_ip(ip):
            raise UnsafeURLError(f"host {host!r} resolves to blocked address {ip}")


async def safe_fetch_bytes(
    url: str,
    *,
    max_bytes: int,
    timeout_seconds: float,
    user_agent: str = "DocsRAG/0.1",
    http_client: httpx.AsyncClient | None = None,
) -> tuple[bytes, str]:
    """Fetch a URL with full SSRF + size + redirect safety.

    Returns (body_bytes, content_type). Streams the body so an attacker that
    keeps a slow stream open cannot fill memory beyond `max_bytes`.

    Redirects are followed manually so each hop is re-validated against the
    SSRF allowlist (httpx.follow_redirects=True would happily redirect to
    169.254.169.254).
    """
    assert_url_is_safe(url)
    owns = http_client is None
    client = http_client or httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_seconds),
        follow_redirects=False,
    )
    try:
        current = url
        for _ in range(5):
            assert_url_is_safe(current)
            async with client.stream(
                "GET", current, headers={"User-Agent": user_agent}
            ) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    next_url = response.headers.get("location")
                    if not next_url:
                        raise UnsafeURLError("redirect without location header")
                    current = next_url
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                buf = bytearray()
                async for chunk in response.aiter_bytes():
                    buf.extend(chunk)
                    if len(buf) > max_bytes:
                        raise UnsafeURLError(f"response exceeded max_bytes={max_bytes}")
                return bytes(buf), content_type
        raise UnsafeURLError("too many redirects")
    finally:
        if owns:
            await client.aclose()


def looks_like_pdf_bytes(data: bytes) -> bool:
    """Magic-byte check for PDF. Cheap defense against mislabeled uploads."""
    return data[:5] == b"%PDF-"


def auth_required(settings: Settings) -> object:
    """FastAPI dependency that enforces Bearer auth when AUTH_BEARER_TOKEN is set.

    When unset (the default for the local demo), all endpoints are open.
    Returns a callable that FastAPI can use via Depends().
    """
    from fastapi import Header, HTTPException, status

    expected = settings.auth_bearer_token

    async def _check(
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> None:
        if expected is None:
            return  # auth disabled
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
        token = authorization[len("Bearer ") :].strip()
        if token != expected:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid bearer token")

    return _check
