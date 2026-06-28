import os

os.environ.setdefault("LLM_PROVIDER", "mock")

import pytest

from src.config import Settings
from src.generate_data import seed


@pytest.fixture
def settings(tmp_path) -> Settings:
    db = str(tmp_path / "store.db")
    seed(db)
    return Settings(llm_provider="mock", db_path=db, max_tool_steps=4)
