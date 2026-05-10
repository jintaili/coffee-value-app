from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_EXTRACTION_MODEL = "gpt-4o-mini"
DEFAULT_WEB_SEARCH_MODEL = "gpt-5.5"
DEFAULT_MAX_PAGE_TEXT_CHARS = 60_000


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    extraction_model: str
    web_search_model: str
    max_page_text_chars: int


def load_settings(*, load_env_file: bool = True) -> Settings:
    if load_env_file:
        load_dotenv(dotenv_path=find_dotenv_path(), override=False)
    return Settings(
        openai_api_key=os.environ.get("OPENAI_API_KEY") or None,
        extraction_model=os.environ.get("OPENAI_EXTRACTION_MODEL", DEFAULT_EXTRACTION_MODEL),
        web_search_model=os.environ.get("OPENAI_WEB_SEARCH_MODEL", DEFAULT_WEB_SEARCH_MODEL),
        max_page_text_chars=parse_int_env("COFFEE_VALUE_MAX_PAGE_TEXT_CHARS", DEFAULT_MAX_PAGE_TEXT_CHARS),
    )


def find_dotenv_path() -> Path | None:
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        return cwd_env
    repo_env = Path(__file__).resolve().parents[2] / ".env"
    if repo_env.exists():
        return repo_env
    return None


def parse_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default
