from __future__ import annotations

from urllib.parse import urlparse


DOMAIN_COUNTRY_OVERRIDES = {
    "onyxcoffeelab.com": "United States",
    "www.onyxcoffeelab.com": "United States",
    "hydrangea.coffee": "United States",
    "www.hydrangea.coffee": "United States",
}


def infer_roaster_country_from_url(url: str) -> tuple[str, str] | None:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    if not host:
        return None
    if host in DOMAIN_COUNTRY_OVERRIDES:
        return DOMAIN_COUNTRY_OVERRIDES[host], f"known roaster domain {host}"
    return None
