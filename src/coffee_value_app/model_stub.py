from __future__ import annotations

from coffee_value_app.schemas import (
    ExtractedPrice,
    PredictionResult,
    PricePrediction,
    RatingPrediction,
    ValuePrediction,
)


MODEL_STUB_VERSION = "stub"


def predict_stub(price: ExtractedPrice) -> PredictionResult:
    return PredictionResult(
        rating=RatingPrediction(
            predicted=None,
            interval_low=None,
            interval_high=None,
            model_version=MODEL_STUB_VERSION,
        ),
        price=PricePrediction(
            predicted_price_100g_usd=None,
            predicted_bag_price_usd=None,
            interval_low=None,
            interval_high=None,
            model_version=MODEL_STUB_VERSION,
        ),
        value=ValuePrediction(
            verdict=value_verdict_without_models(price),
            listed_vs_predicted_delta_pct=None,
        ),
    )


def value_verdict_without_models(price: ExtractedPrice) -> str:
    if price.price_100g_usd is None:
        return "model_not_available_price_missing"
    return "model_not_available"

