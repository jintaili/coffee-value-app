from coffee_value_app.config import (
    DEFAULT_EXTRACTION_MODEL,
    DEFAULT_MAX_PAGE_TEXT_CHARS,
    DEFAULT_WEB_SEARCH_MODEL,
    load_settings,
)


def test_load_settings_uses_defaults_without_env(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_EXTRACTION_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_WEB_SEARCH_MODEL", raising=False)
    monkeypatch.delenv("COFFEE_VALUE_MAX_PAGE_TEXT_CHARS", raising=False)

    settings = load_settings(load_env_file=False)

    assert settings.openai_api_key is None
    assert settings.extraction_model == DEFAULT_EXTRACTION_MODEL
    assert settings.web_search_model == DEFAULT_WEB_SEARCH_MODEL
    assert settings.max_page_text_chars == DEFAULT_MAX_PAGE_TEXT_CHARS


def test_load_settings_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_EXTRACTION_MODEL", "gpt-test")
    monkeypatch.setenv("OPENAI_WEB_SEARCH_MODEL", "gpt-search-test")
    monkeypatch.setenv("COFFEE_VALUE_MAX_PAGE_TEXT_CHARS", "1234")

    settings = load_settings(load_env_file=False)

    assert settings.openai_api_key == "test-key"
    assert settings.extraction_model == "gpt-test"
    assert settings.web_search_model == "gpt-search-test"
    assert settings.max_page_text_chars == 1234
