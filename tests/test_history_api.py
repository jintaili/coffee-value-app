from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from coffee_value_app.analysis import FixtureAnalysisService
from coffee_value_app.history import HistoryItem
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


class FakeHistoryStore:
    def __init__(self) -> None:
        self.saved_successes = []
        self.saved_errors = []
        self.items = []

    def save_success(self, *, url, response):
        self.saved_successes.append({"url": url, "response": response})
        return UUID("00000000-0000-0000-0000-000000000001")

    def save_error(self, *, url, error):
        self.saved_errors.append({"url": url, "error": error})
        return UUID("00000000-0000-0000-0000-000000000002")

    def list_recent(self, *, limit=25):
        return self.items[:limit]


def test_analyze_api_records_success_history() -> None:
    app = create_app()
    history_store = FakeHistoryStore()
    app.state.history_store = history_store
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
    assert len(history_store.saved_successes) == 1
    saved = history_store.saved_successes[0]
    assert saved["url"].startswith("https://onyxcoffeelab.com/products/")
    assert saved["response"]["coffee"]["coffee_name"] == "Peru La Margarita Gesha"


def test_history_api_returns_recent_items() -> None:
    app = create_app()
    history_store = FakeHistoryStore()
    history_store.items = [
        HistoryItem(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            created_at=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
            url="https://example.com/coffee",
            status="error",
            response=None,
            error="Fetch failed",
        )
    ]
    app.state.history_store = history_store
    client = TestClient(app)

    response = client.get("/api/history")

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "created_at": "2026-05-11T12:00:00Z",
            "url": "https://example.com/coffee",
            "status": "error",
            "response": None,
            "error": "Fetch failed",
        }
    ]
