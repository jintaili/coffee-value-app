import pytest

from coffee_value_app.fetcher import (
    BlockedUrlError,
    InvalidUrlError,
    validate_public_http_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/product",
        "file:///etc/passwd",
        "https://user:pass@example.com/product",
        "https:///missing-host",
    ],
)
def test_validate_public_http_url_rejects_invalid_urls(url: str) -> None:
    with pytest.raises(InvalidUrlError):
        validate_public_http_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/product",
        "http://127.0.0.1/product",
        "http://10.0.0.1/product",
        "http://172.16.0.1/product",
        "http://192.168.1.1/product",
        "http://[::1]/product",
    ],
)
def test_validate_public_http_url_rejects_private_destinations(url: str) -> None:
    with pytest.raises(BlockedUrlError):
        validate_public_http_url(url)


def test_validate_public_http_url_accepts_public_https_url() -> None:
    assert validate_public_http_url("https://onyxcoffeelab.com/products/example") == (
        "https://onyxcoffeelab.com/products/example"
    )
