from types import SimpleNamespace

import pytest

from coffee_value_app.roaster_resolver import (
    RoasterCountryResolution,
    apply_roaster_country_resolution,
    parse_resolution_response,
)
from coffee_value_app.schemas import ExtractedCoffee, ProcessMethod, Variety


def test_parse_resolution_response_handles_dict() -> None:
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        parsed={
                            "roaster_country": "United States",
                            "confidence": "high",
                            "evidence_url": "https://example.com/about",
                            "evidence_title": "About Example Roaster",
                            "evidence_snippet": "Example Roaster is based in Arkansas.",
                        },
                    )
                ],
            )
        ]
    )

    resolution = parse_resolution_response(response)

    assert resolution.roaster_country == "United States"
    assert resolution.evidence_url == "https://example.com/about"


def test_apply_roaster_country_resolution_updates_unknown_country() -> None:
    coffee = ExtractedCoffee(
        coffee_name="Example Coffee",
        roaster="Example Roaster",
        roaster_location=None,
        roaster_country="unknown",
        origin_country="Colombia",
        origin_region="Cauca",
        process_method=[ProcessMethod.WASHED],
        variety=[Variety.GESHA],
        producer_or_farm=None,
        altitude=None,
        is_blend=False,
        is_espresso=False,
        is_decaf=False,
        sensory_text="Mango.",
        producer_text="Colombia coffee.",
        source_snippets=[],
    )
    resolution = RoasterCountryResolution(
        roaster_country="United States",
        confidence="high",
        evidence_url="https://example.com/about",
        evidence_title="About",
        evidence_snippet="Example Roaster is based in Arkansas.",
    )

    updated = apply_roaster_country_resolution(coffee, resolution)

    assert updated.roaster_country == "United States"
    assert updated.source_snippets[-1].field == "roaster_country"


@pytest.mark.parametrize("country", ["", "unknown"])
def test_apply_roaster_country_resolution_ignores_unknown_resolution(country: str) -> None:
    coffee = ExtractedCoffee(
        coffee_name=None,
        roaster=None,
        roaster_location=None,
        roaster_country="unknown",
        origin_country="unknown",
        origin_region="unknown",
        process_method=[ProcessMethod.UNKNOWN],
        variety=[Variety.UNKNOWN],
        producer_or_farm=None,
        altitude=None,
        is_blend=False,
        is_espresso=False,
        is_decaf=False,
        sensory_text="",
        producer_text="",
        source_snippets=[],
    )
    resolution = RoasterCountryResolution(
        roaster_country=country,
        confidence="low",
        evidence_url=None,
        evidence_title=None,
        evidence_snippet=None,
    )

    assert apply_roaster_country_resolution(coffee, resolution) == coffee

