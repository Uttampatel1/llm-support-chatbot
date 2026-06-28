"""Configuration from environment / ``.env``."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _get(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    llm_provider: str = _get("LLM_PROVIDER", "mock")  # "mock" | "gemini"
    gemini_api_key: str = _get("GEMINI_API_KEY", "")
    gemini_model: str = _get("GEMINI_MODEL", "gemini-2.0-flash")
    db_path: str = _get("DB_PATH", "data/store.db")
    max_tool_steps: int = int(_get("MAX_TOOL_STEPS", "4"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
