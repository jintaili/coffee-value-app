from datetime import timedelta

import pytest

from coffee_value_app.currency import CurrencyConversionError, CurrencyConverter
from coffee_value_app.schemas import ExtractedPrice


class FakeRateClient:
    def __init__(self, rate: float = 1.2, date: str = "2026-05-10") -> None:
        self.rate = rate
        self.date = date
        self.calls: list[tuple[str, str]] = []

    async def latest_rate(self, base: str, quote: str) -> tuple[float, str | None]:
        self.calls.append((base, quote))
        return self.rate, self.date


class FailingRateClient:
    async def latest_rate(self, base: str, quote: str) -> tuple[float, str | None]:
        raise CurrencyConversionError("missing rate")


def price(**overrides) -> ExtractedPrice:
    values = {
        "listed_price": 10.0,
        "listed_currency": "USD",
        "bag_size_value": 100.0,
        "bag_size_unit": "g",
        "package_grams": 100.0,
        "price_100g_usd": None,
        "assumptions": [],
    }
    values.update(overrides)
    return ExtractedPrice(**values)


@pytest.mark.anyio
async def test_usd_price_100g_is_computed_without_external_rate() -> None:
    client = FakeRateClient()
    converter = CurrencyConverter(client=client)

    converted = await converter.normalize_to_usd(price(listed_price=12.5, package_grams=250.0))

    assert converted.listed_price == 12.5
    assert converted.listed_currency == "USD"
    assert converted.price_100g_usd == 5.0
    assert client.calls == []


@pytest.mark.anyio
async def test_non_usd_price_is_converted_to_usd() -> None:
    converter = CurrencyConverter(client=FakeRateClient(rate=1.25, date="2026-05-09"))

    converted = await converter.normalize_to_usd(
        price(listed_price=20.0, listed_currency="EUR", package_grams=250.0)
    )

    assert converted.listed_price == 25.0
    assert converted.listed_currency == "USD"
    assert converted.original_listed_price == 20.0
    assert converted.original_listed_currency == "EUR"
    assert converted.price_100g_usd == 10.0
    assert converted.assumptions == [
        "converted 20.00 EUR to 25.00 USD using Frankfurter rate from 2026-05-09"
    ]


@pytest.mark.anyio
async def test_rates_are_cached() -> None:
    client = FakeRateClient(rate=1.1)
    converter = CurrencyConverter(client=client, ttl=timedelta(hours=1))

    await converter.normalize_to_usd(price(listed_currency="CAD"))
    await converter.normalize_to_usd(price(listed_currency="CAD"))

    assert client.calls == [("CAD", "USD")]


@pytest.mark.anyio
async def test_failed_conversion_keeps_original_price_and_records_assumption() -> None:
    converter = CurrencyConverter(client=FailingRateClient())

    converted = await converter.normalize_to_usd(price(listed_price=20.0, listed_currency="GBP"))

    assert converted.listed_price == 20.0
    assert converted.listed_currency == "GBP"
    assert converted.price_100g_usd is None
    assert converted.assumptions == ["currency conversion unavailable for GBP; price left unconverted"]
