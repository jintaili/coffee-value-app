from types import SimpleNamespace

import pytest

from coffee_value_app.extractor import OpenAILLMExtractor, parse_structured_response, trim_page_text
from coffee_value_app.schemas import ExtractedCoffee, ExtractedPrice, PageExtraction, QualityReport


class FakeResponses:
    def __init__(self, parsed: PageExtraction) -> None:
        self.kwargs = None
        self.parsed = parsed

    async def parse(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="message",
                    content=[SimpleNamespace(type="output_text", parsed=self.parsed)],
                )
            ]
        )


class FakeClient:
    def __init__(self, parsed: PageExtraction) -> None:
        self.responses = FakeResponses(parsed)


def test_trim_page_text_keeps_start_and_end_for_long_pages() -> None:
    text = "start\n" + ("middle\n" * 1000) + "end"

    trimmed = trim_page_text(text, max_chars=100)

    assert trimmed.startswith("start")
    assert "middle of page omitted" in trimmed
    assert trimmed.endswith("end")


@pytest.mark.anyio
async def test_openai_extractor_requests_structured_page_extraction() -> None:
    parsed = PageExtraction(
        coffee=ExtractedCoffee(
            coffee_name="Peru La Margarita Gesha",
            roaster="Onyx Coffee Lab",
            roaster_location=None,
            roaster_country="United States",
            origin_country="Peru",
            origin_region="La Convencion, Cusco",
            process_method=["washed"],
            variety=["gesha"],
            producer_or_farm="La Margarita Coffee Reserve",
            altitude="1900 MASL",
            is_blend=False,
            is_espresso=False,
            is_decaf=False,
            sensory_text="Jasmine, white grape, black tea.",
            producer_text="Gesha from southern Peru.",
            source_snippets=[{"field": "origin", "snippet": "Peru La Margarita Gesha"}],
        ),
        price=ExtractedPrice(
            listed_price=26,
            listed_currency="USD",
            bag_size_value=10,
            bag_size_unit="oz",
            package_grams=283.495231,
            price_100g_usd=9.17,
            assumptions=[],
        ),
        quality=QualityReport(extraction_quality="good", missing_fields=[], warnings=[]),
    )
    client = FakeClient(parsed)
    extractor = OpenAILLMExtractor(client=client, model="gpt-test")

    result = await extractor.extract(
        url="https://onyxcoffeelab.com/products/peru-la-margarita-gesha-26",
        page_text="Peru La Margarita Gesha. 10 oz. $26. Jasmine, white grape, black tea.",
    )

    assert result == parsed
    assert client.responses.kwargs["model"] == "gpt-test"
    assert client.responses.kwargs["text_format"] is PageExtraction
    assert "Peru La Margarita Gesha" in client.responses.kwargs["input"][1]["content"]


def test_parse_structured_response_handles_plain_dict() -> None:
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        parsed={
                            "coffee": {
                                "coffee_name": None,
                                "roaster": None,
                                "roaster_location": None,
                                "roaster_country": "unknown",
                                "origin_country": "unknown",
                                "origin_region": "unknown",
                                "process_method": ["unknown"],
                                "variety": ["unknown"],
                                "producer_or_farm": None,
                                "altitude": None,
                                "is_blend": False,
                                "is_espresso": False,
                                "is_decaf": False,
                                "sensory_text": "",
                                "producer_text": "",
                                "source_snippets": [],
                            },
                            "price": {
                                "listed_price": None,
                                "listed_currency": None,
                                "bag_size_value": None,
                                "bag_size_unit": None,
                                "package_grams": None,
                                "price_100g_usd": None,
                                "assumptions": [],
                            },
                            "quality": {"extraction_quality": "poor", "missing_fields": [], "warnings": []},
                        },
                    )
                ],
            )
        ]
    )

    parsed = parse_structured_response(response)

    assert parsed.coffee.origin_country == "unknown"
    assert parsed.quality.extraction_quality == "poor"
