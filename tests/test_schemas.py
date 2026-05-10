from coffee_value_app.schemas import ExtractedCoffee, ExtractedPrice, ProcessMethod, Variety, to_model_input


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
