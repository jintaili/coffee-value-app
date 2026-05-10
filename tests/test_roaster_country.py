from coffee_value_app.roaster_country import infer_roaster_country_from_url


def test_infer_roaster_country_from_known_domain() -> None:
    assert infer_roaster_country_from_url("https://onyxcoffeelab.com/products/x") == (
        "United States",
        "known roaster domain onyxcoffeelab.com",
    )


def test_infer_roaster_country_returns_none_for_generic_unknown_domain() -> None:
    assert infer_roaster_country_from_url("https://example.com/products/x") is None


def test_infer_roaster_country_does_not_use_country_code_tlds() -> None:
    assert infer_roaster_country_from_url("https://example.com.au/products/x") is None
