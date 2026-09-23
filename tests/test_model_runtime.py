import pickle

import pytest

from coffee_value_app.model_runtime import (
    ModelArtifactContractError,
    ModelService,
    PRICE_MODEL_PATH,
    RATING_MODEL_PATH,
    load_pickle,
)


def test_rating_artifact_is_lightweight_tfidf_model() -> None:
    artifact = load_pickle(RATING_MODEL_PATH)

    assert artifact["config"]["encoder"] == "tfidf"
    assert artifact["config"]["model"] == "ridge"
    assert artifact["config"]["alpha"] == 1.0


def test_model_service_loads_lightweight_artifacts() -> None:
    service = ModelService()

    assert service.rating_artifact["config"]["encoder"] == "tfidf"
    assert service.price_artifact["config"]["model"] == "elasticnet"
    assert service.rating_model_version.startswith("rating:")
    assert service.price_model_version.startswith("price:")


def test_model_service_rejects_incompatible_feature_contract(tmp_path) -> None:
    artifact = load_pickle(RATING_MODEL_PATH)
    artifact["config"] = {**artifact["config"], "structured_fields": ["origin_country"]}
    incompatible_path = tmp_path / "rating.pkl"
    incompatible_path.write_bytes(pickle.dumps(artifact))

    with pytest.raises(ModelArtifactContractError, match="structured_fields"):
        ModelService(rating_model_path=incompatible_path, price_model_path=PRICE_MODEL_PATH)


def test_model_service_rejects_feature_dimension_mismatch(tmp_path) -> None:
    artifact = load_pickle(PRICE_MODEL_PATH)
    artifact["weights"] = artifact["weights"][:-1]
    incompatible_path = tmp_path / "price.pkl"
    incompatible_path.write_bytes(pickle.dumps(artifact))

    with pytest.raises(ModelArtifactContractError, match="encoder emits"):
        ModelService(rating_model_path=RATING_MODEL_PATH, price_model_path=incompatible_path)
