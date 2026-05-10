from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_BYTES = 2_000_000
DEFAULT_MAX_REDIRECTS = 5


class FetchError(Exception):
    """Base class for product page fetch failures."""


class InvalidUrlError(FetchError):
    """Raised when a URL is malformed or uses an unsupported scheme."""


class BlockedUrlError(FetchError):
    """Raised when a URL points to a private or otherwise unsafe destination."""


class FetchTimeoutError(FetchError):
    """Raised when fetching a URL times out."""


class FetchTooLargeError(FetchError):
    """Raised when the response body exceeds the configured byte limit."""


@dataclass(frozen=True)
class FetchedPage:
    url: str
    final_url: str
    status_code: int
    content_type: str
    text: str


def validate_public_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise InvalidUrlError("Only http and https URLs are supported.")
    if not parsed.hostname:
        raise InvalidUrlError("URL must include a hostname.")
    if parsed.username or parsed.password:
        raise InvalidUrlError("URLs with embedded credentials are not supported.")
    if _hostname_is_blocked(parsed.hostname):
        raise BlockedUrlError("URL hostname is not publicly fetchable.")
    return url


def resolve_public_addresses(hostname: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise InvalidUrlError("URL hostname could not be resolved.") from exc

    addresses = sorted({info[4][0] for info in infos})
    if not addresses:
        raise InvalidUrlError("URL hostname could not be resolved.")
    for address in addresses:
        if _ip_is_blocked(address):
            raise BlockedUrlError("URL resolves to a private or reserved address.")
    return addresses


async def fetch_product_page(
    url: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
) -> FetchedPage:
    validate_public_http_url(url)
    resolve_public_addresses(urlparse(url).hostname or "")

    async with httpx.AsyncClient(
        follow_redirects=True,
        max_redirects=max_redirects,
        timeout=httpx.Timeout(timeout_seconds),
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    ) as client:
        try:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                final_host = urlparse(str(response.url)).hostname or ""
                if final_host:
                    validate_public_http_url(str(response.url))
                    resolve_public_addresses(final_host)

                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise FetchTooLargeError("Response body exceeded maximum allowed size.")
                    chunks.append(chunk)

                body = b"".join(chunks)
        except httpx.TimeoutException as exc:
            raise FetchTimeoutError("Fetching URL timed out.") from exc
        except httpx.TooManyRedirects as exc:
            raise BlockedUrlError("URL exceeded redirect limit.") from exc
        except httpx.HTTPStatusError as exc:
            raise FetchError(f"Upstream returned HTTP {exc.response.status_code}.") from exc
        except httpx.HTTPError as exc:
            raise FetchError("Failed to fetch URL.") from exc

    encoding = response.encoding or "utf-8"
    return FetchedPage(
        url=url,
        final_url=str(response.url),
        status_code=response.status_code,
        content_type=response.headers.get("content-type", ""),
        text=body.decode(encoding, errors="replace"),
    )


def _hostname_is_blocked(hostname: str) -> bool:
    normalized = hostname.strip().lower().rstrip(".")
    if normalized in {"localhost", "localhost.localdomain"}:
        return True
    try:
        return _ip_is_blocked(normalized)
    except ValueError:
        return False


def _ip_is_blocked(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return any(
        [
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        ]
    )
