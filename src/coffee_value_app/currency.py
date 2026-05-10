from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol

import httpx

from coffee_value_app.schemas import ExtractedPrice


FRANKFURTER_LATEST_URL = "https://api.frankfurter.dev/v1/latest"
RATE_TTL = timedelta(hours=12)


class CurrencyConversionError(RuntimeError):
    pass


class RateClient(Protocol):
    async def latest_rate(self, base: str, quote: str) -> tuple[float, str | None]:
        pass


@dataclass
class FrankfurterRateClient:
    timeout_seconds: float = 8.0

    async def latest_rate(self, base: str, quote: str) -> tuple[float, str | None]:
        params = {"base": base.upper(), "symbols": quote.upper()}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(FRANKFURTER_LATEST_URL, params=params)
        response.raise_for_status()
        payload = response.json()
        rates = payload.get("rates") or {}
        rate = rates.get(quote.upper())
        if not isinstance(rate, int | float) or rate <= 0:
            raise CurrencyConversionError(f"No {base}->{quote} rate returned")
        date = payload.get("date")
        return float(rate), str(date) if date else None


@dataclass
class CurrencyConverter:
    client: RateClient = field(default_factory=FrankfurterRateClient)
    ttl: timedelta = RATE_TTL
    _cache: dict[tuple[str, str], tuple[float, str | None, datetime]] = field(default_factory=dict)

    async def normalize_to_usd(self, price: ExtractedPrice) -> ExtractedPrice:
        if price.listed_price is None or price.package_grams is None:
            return price.model_copy(update={"currency_conversion_status": "missing_data"})

        currency = normalize_currency(price.listed_currency)
        if currency == "USD":
            return ensure_usd_price_100g(price).model_copy(update={"currency_conversion_status": "not_needed"})
        if currency is None:
            return price.model_copy(update={"currency_conversion_status": "missing_data"})

        try:
            rate, rate_date = await self.get_rate(currency, "USD")
        except (httpx.HTTPError, CurrencyConversionError, ValueError):
            return price.model_copy(
                update={
                    "currency_conversion_status": "failed",
                    "assumptions": [
                        *price.assumptions,
                        f"currency conversion unavailable for {currency}; price left unconverted",
                    ]
                }
            )

        original_price = price.listed_price
        converted_price = round(original_price * rate, 2)
        converted_100g = round(converted_price / price.package_grams * 100.0, 2)
        date_text = f" rate from {rate_date}" if rate_date else " latest rate"
        return price.model_copy(
            update={
                "listed_price": converted_price,
                "listed_currency": "USD",
                "original_listed_price": price.original_listed_price or original_price,
                "original_listed_currency": price.original_listed_currency or currency,
                "currency_conversion_status": "converted",
                "currency_conversion_rate": rate,
                "currency_conversion_date": rate_date,
                "price_100g_usd": converted_100g,
                "assumptions": [
                    *price.assumptions,
                    f"converted {original_price:.2f} {currency} to {converted_price:.2f} USD using Frankfurter{date_text}",
                ],
            }
        )

    async def get_rate(self, base: str, quote: str) -> tuple[float, str | None]:
        key = (base.upper(), quote.upper())
        now = datetime.now(timezone.utc)
        cached = self._cache.get(key)
        if cached is not None:
            rate, rate_date, fetched_at = cached
            if now - fetched_at < self.ttl:
                return rate, rate_date
        rate, rate_date = await self.client.latest_rate(*key)
        self._cache[key] = (rate, rate_date, now)
        return rate, rate_date


def ensure_usd_price_100g(price: ExtractedPrice) -> ExtractedPrice:
    if price.price_100g_usd is not None or price.listed_price is None or price.package_grams is None:
        return price
    return price.model_copy(update={"price_100g_usd": round(price.listed_price / price.package_grams * 100.0, 2)})


def normalize_currency(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().upper()
    return cleaned or None
