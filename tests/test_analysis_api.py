from pathlib import Path

from fastapi.testclient import TestClient

from coffee_value_app.analysis import FixtureAnalysisService
from coffee_value_app.main import create_app
from coffee_value_app.schemas import PredictionResult, PricePrediction, RatingPrediction, ValuePrediction


class FakeModelService:
    def predict(self, model_input, listed_price):
        return PredictionResult(
            rating=RatingPrediction(predicted=93.2, interval_low=91.6, interval_high=94.8, model_version="fake"),
            price=PricePrediction(
                predicted_price_100g_usd=18.5,
                predicted_bag_price_usd=52.45,
                interval_low=11.1,
                interval_high=29.6,
                model_version="fake",
            ),
            value=ValuePrediction(verdict="expensive_for_predicted_quality", listed_vs_predicted_delta_pct=33.4),
        )


def test_analyze_api_returns_fixture_response_shape() -> None:
    app = create_app()
    app.state.analysis_service = FixtureAnalysisService(
        Path("tests/fixtures/onyx_extraction.json"),
        model_service=FakeModelService(),
    )
    client = TestClient(app)

    response = client.post(
        "/api/analyze",
        json={
            "url": "https://onyxcoffeelab.com/products/peru-la-margarita-gesha-26?variant=42842298646626"
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["coffee"]["coffee_name"] == "Peru La Margarita Gesha"
    assert data["coffee"]["roaster_country"] == "United States"
    assert data["price"]["package_grams"] == 283.495
    assert data["model_input"] == {
        "origin_country": "Peru",
        "process_method": "washed",
        "variety": "gesha",
        "is_blend": "0",
        "is_espresso": "1",
        "is_decaf": "0",
        "producer_or_farm_present": "1",
        "altitude_present": "1",
        "roaster_country": "United States",
        "sensory_text": "Jasmine, White Grape, Black Tea",
        "producer_text": "This delicate and sweet Gesha variety is produced in Southern Peru by the Solorzano Family.",
        "package_grams": 283.495,
    }
    assert data["prediction"]["rating"]["predicted"] == 93.2
    assert data["prediction"]["rating"]["model_version"] == "fake"
    assert data["prediction"]["price"]["predicted_price_100g_usd"] == 18.5
    assert data["prediction"]["value"]["verdict"] == "expensive_for_predicted_quality"
