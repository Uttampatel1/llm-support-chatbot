"""Tests for the human-handoff escalation guardrail."""
from __future__ import annotations

from src.agent import SupportAgent
from src.database import connect
from src.escalation import detect_escalation
from src.tools import ToolContext, escalate_to_human


# --- detector unit tests ----------------------------------------------------
def test_detect_explicit_human_request():
    d = detect_escalation("Can I please speak to a human agent?")
    assert d.escalate and d.category == "explicit_request"
    assert d.priority == "normal"


def test_detect_frustration():
    d = detect_escalation("This bot is absolutely useless and terrible!")
    assert d.escalate and d.category == "frustration"
    assert d.priority == "high"


def test_detect_repeated_failure_threshold():
    assert not detect_escalation("where is my order", recent_tool_failures=1).escalate
    d = detect_escalation("where is my order", recent_tool_failures=2)
    assert d.escalate and d.category == "repeated_failure"


def test_normal_message_does_not_escalate():
    assert not detect_escalation("What is your return policy?").escalate


# --- tool persistence -------------------------------------------------------
def test_escalate_tool_opens_ticket(settings):
    ctx = ToolContext(db_path=settings.db_path, email="alice@example.com")
    info = escalate_to_human(ctx, "angry customer", category="frustration")
    assert info["ticket_id"].startswith("TKT-")
    assert info["priority"] == "high"
    with connect(settings.db_path) as conn:
        row = conn.execute(
            "SELECT * FROM support_tickets WHERE ticket_id = ?", (info["ticket_id"],)
        ).fetchone()
    assert row is not None
    assert row["status"] == "open"
    assert row["email"] == "alice@example.com"


# --- agent integration ------------------------------------------------------
def test_agent_escalates_on_explicit_request(settings):
    agent = SupportAgent(settings)
    res = agent.chat("Just connect me to a human, please.")
    assert res.escalated
    assert res.ticket_id and res.ticket_id.startswith("TKT-")
    assert res.tool_calls[-1]["name"] == "escalate_to_human"
    assert "ticket" in res.reply.lower()


def test_agent_escalates_on_frustration(settings):
    agent = SupportAgent(settings)
    res = agent.chat("This is the worst service ever, absolutely ridiculous!!!")
    assert res.escalated
    assert res.tool_calls[-1]["result"]["priority"] == "high"


def test_agent_does_not_escalate_normal_question(settings):
    agent = SupportAgent(settings)
    res = agent.chat("what is your return policy?")
    assert not res.escalated
