from coffee_value_app.model_runtime import ROOT, resolve_embedding_model_path


def test_resolve_embedding_model_path_uses_vendored_model() -> None:
    expected = ROOT / "artifacts" / "embedding_models" / "all-MiniLM-L6-v2"

    assert resolve_embedding_model_path("sentence-transformers/all-MiniLM-L6-v2") == str(expected)


def test_resolve_embedding_model_path_leaves_unknown_model_unchanged() -> None:
    assert resolve_embedding_model_path("sentence-transformers/other-model") == "sentence-transformers/other-model"

