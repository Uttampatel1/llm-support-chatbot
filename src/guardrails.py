"""Lightweight guardrails: identity capture and basic input hygiene."""
from __future__ import annotations

import re

from .database import connect

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
MAX_INPUT_CHARS = 1000


def extract_email(text: str) -> str | None:
    m = EMAIL_RE.search(text)
    return m.group(0).lower() if m else None


def customer_exists(db_path: str, email: str) -> bool:
    with connect(db_path) as conn:
        return conn.execute(
            "SELECT 1 FROM customers WHERE email = ?", (email,)
        ).fetchone() is not None


def sanitize_input(text: str) -> str:
    text = text.strip()
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS]
    return text
