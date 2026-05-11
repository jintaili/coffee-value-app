from coffee_value_app.model_runtime import ModelService, RATING_MODEL_PATH, load_pickle


def test_rating_artifact_is_lightweight_tfidf_model() -> None:
    artifact = load_pickle(RATING_MODEL_PATH)

    assert artifact["config"]["encoder"] == "tfidf"
    assert artifact["config"]["model"] == "ridge"
    assert artifact["config"]["alpha"] == 1.0


def test_model_service_loads_lightweight_artifacts() -> None:
    service = ModelService()

    assert service.rating_artifact["config"]["encoder"] == "tfidf"
    assert service.price_artifact["config"]["model"] == "elasticnet"
