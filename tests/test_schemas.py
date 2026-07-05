from coffee_value_app.schemas import (
    ExtractedCoffee,
    ExtractedPrice,
    ProcessMethod,
    Variety,
    map_process_terms,
    map_variety_terms,
    to_model_input,
)


def test_model_input_matches_training_field_format() -> None:
    coffee = ExtractedCoffee(
        coffee_name="Peru La Margarita Gesha",
        roaster="Onyx Coffee Lab",
        roaster_location=None,
        roaster_country="United States",
        origin_country="Peru",
        origin_region="Cusco",
        process_method=[ProcessMethod.WASHED],
        variety=[Variety.GESHA],
        producer_or_farm="Solorzano Family, La Margarita Coffee Reserve",
        altitude="1900 MASL",
        is_blend=False,
        is_espresso=True,
        is_decaf=False,
        sensory_text="Jasmine, white grape, black tea, refined.",
        producer_text="Produced in Southern Peru by the Solorzano Family.",
        source_snippets=[],
    )
    price = ExtractedPrice(
        listed_price=26,
        listed_currency="USD",
        bag_size_value=10,
        bag_size_unit="oz",
        package_grams=283.495231,
        price_100g_usd=9.17,
        assumptions=[],
    )

    model_input = to_model_input(coffee, price)

    assert model_input.model_dump() == {
        "origin_country": "Peru",
        "process_method": "washed",
        "variety": "gesha",
        "is_blend": "0",
        "is_espresso": "1",
        "is_decaf": "0",
        "producer_or_farm_present": "1",
        "altitude_present": "1",
        "roaster_country": "United States",
        "sensory_text": "Jasmine, white grape, black tea, refined.",
        "producer_text": "Produced in Southern Peru by the Solorzano Family.",
        "package_grams": 283.495231,
    }


def test_unknown_list_values_are_not_mixed_with_specific_values() -> None:
    coffee = ExtractedCoffee(
        coffee_name=None,
        roaster=None,
        roaster_location=None,
        roaster_country="unknown",
        origin_country="unknown",
        origin_region="unknown",
        process_method=["unknown", "washed"],
        variety=["unknown", "gesha"],
        producer_or_farm=None,
        altitude=None,
        is_blend=False,
        is_espresso=False,
        is_decaf=False,
        sensory_text="",
        producer_text="",
        source_snippets=[],
    )

    assert coffee.process_method == [ProcessMethod.WASHED]
    assert coffee.variety == [Variety.GESHA]


def test_rare_variety_is_kept_verbatim_and_lumps_to_unknown_for_model() -> None:
    assert map_variety_terms(["SL-9"]) == [Variety.UNKNOWN]
    assert map_variety_terms(["Ombligon"]) == [Variety.UNKNOWN]

    coffee = ExtractedCoffee(
        coffee_name="Gilber Huayllas",
        roaster="Moonwake",
        roaster_location=None,
        roaster_country="United States",
        origin_country="Peru",
        origin_region="unknown",
        process_method=["anaerobic washed"],
        variety=["SL-9"],
        producer_or_farm=None,
        altitude=None,
        is_blend=False,
        is_espresso=False,
        is_decaf=False,
        sensory_text="",
        producer_text="",
        source_snippets=[],
    )
    price = ExtractedPrice(
        listed_price=None,
        listed_currency=None,
        bag_size_value=None,
        bag_size_unit=None,
        package_grams=None,
        price_100g_usd=None,
        assumptions=[],
    )

    model_input = to_model_input(coffee, price)

    assert coffee.variety == ["SL-9"]
    assert model_input.variety == "unknown"
    assert model_input.process_method == "anaerobic|washed"


def test_verbatim_process_terms_map_to_training_vocab() -> None:
    assert map_process_terms(["White Honey"]) == [ProcessMethod.HONEY]
    assert map_process_terms(["giling basah"]) == [ProcessMethod.WET_HULLED]
    assert map_process_terms(["72 hour anaerobic natural"]) == [
        ProcessMethod.ANAEROBIC,
        ProcessMethod.NATURAL,
    ]
    assert map_process_terms(["unknown"]) == [ProcessMethod.UNKNOWN]
    assert map_process_terms([]) == [ProcessMethod.UNKNOWN]


def test_variety_mapping_matches_training_semantics() -> None:
    assert map_variety_terms(["Geisha"]) == [Variety.GESHA]
    assert map_variety_terms(["SL 28", "SL-34"]) == [Variety.SL28, Variety.SL34]
    assert map_variety_terms(["Pink Bourbon"]) == [Variety.PINK_BOURBON, Variety.BOURBON]


def test_new_optional_fields_default_for_legacy_payloads() -> None:
    coffee = ExtractedCoffee(
        coffee_name=None,
        roaster=None,
        roaster_location=None,
        roaster_country="unknown",
        origin_country="unknown",
        origin_region="unknown",
        process_method=["unknown"],
        variety=["unknown"],
        producer_or_farm=None,
        altitude=None,
        is_blend=False,
        is_espresso=False,
        is_decaf=False,
        sensory_text="",
        producer_text="",
        source_snippets=[],
    )

    assert coffee.roast_level is None
    assert coffee.harvest_period is None
    assert coffee.is_coferment_or_infused is False
