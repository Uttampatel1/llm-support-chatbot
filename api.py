"""FastAPI service for the support chatbot.

POST /chat   {session_id, message} -> {reply, tool_calls, authenticated_as}
GET  /health

Each session_id keeps its own conversation memory (and authenticated identity).

Run:  uvicorn api:app --reload
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from pydantic import BaseModel, Field

from src.agent import SupportAgent
from src.config import get_settings
from src.generate_data import seed

settings = get_settings()
if not os.path.exists(settings.db_path):
    seed(settings.db_path)

app = FastAPI(title="LLM Support Chatbot", version="1.0.0")
_sessions: dict[str, SupportAgent] = {}


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


def _agent(session_id: str) -> SupportAgent:
    if session_id not in _sessions:
        _sessions[session_id] = SupportAgent(settings)
    return _sessions[session_id]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": _agent("_probe").provider.name}


@app.post("/chat")
def chat(req: ChatRequest) -> dict:
    result = _agent(req.session_id).chat(req.message)
    return {
        "reply": result.reply,
        "tool_calls": result.tool_calls,
        "authenticated_as": result.authenticated_as,
    }


@app.post("/reset")
def reset(req: ChatRequest) -> dict:
    _sessions.pop(req.session_id, None)
    return {"status": "reset", "session_id": req.session_id}
