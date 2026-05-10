from coffee_value_app.product_data import embedded_product_data_to_text, parse_grams_from_text


def test_embedded_product_data_marks_selected_shopify_variant() -> None:
    html = """
    <script>
    window.ShopifyAnalytics = window.ShopifyAnalytics || {};
    window.ShopifyAnalytics.meta = window.ShopifyAnalytics.meta || {};
    window.ShopifyAnalytics.meta.currency = 'USD';
    var meta = {"product":{"vendor":"Onyx Coffee Lab","variants":[
      {"id":1,"price":1800,"name":"Coffee - 2oz","public_title":"2oz","sku":"SKU-2"},
      {"id":2,"price":7000,"name":"Coffee - 10oz","public_title":"10oz","sku":"SKU-10"},
      {"id":3,"price":12800,"name":"Coffee - 2lbs","public_title":"2lbs","sku":"SKU-2LB"}
    ]}};
    </script>
    """

    text = embedded_product_data_to_text(html, "https://example.com/products/coffee?variant=2")

    assert "id=2" in text
    assert "price=70.00 USD" in text
    assert "package_grams=283.495g" in text
    assert "selected_by_url default_for_inference" in text


def test_embedded_product_data_defaults_to_size_closest_to_10oz() -> None:
    html = """
    <script>
    var meta = {"product":{"variants":[
      {"id":1,"price":2800,"name":"Coffee - 4oz (114g)","public_title":"4oz (114g)"},
      {"id":2,"price":4600,"name":"Coffee - 8oz (227g)","public_title":"8oz (227g)"},
      {"id":3,"price":16000,"name":"Coffee - 2lbs (907g)","public_title":"2lbs (907g)"}
    ]}};
    </script>
    """

    text = embedded_product_data_to_text(html, "https://example.com/products/coffee")

    default_line = next(line for line in text.splitlines() if "default_for_inference" in line)
    assert "id=2" in default_line
    assert "price=46.00" in default_line
    assert "package_grams=226.796g" in default_line or "package_grams=227.000g" in default_line


def test_parse_grams_from_text_supports_common_units() -> None:
    assert parse_grams_from_text("10oz") == 283.495231
    assert parse_grams_from_text("250 g") == 250
    assert parse_grams_from_text("2lbs") == 907.18474
