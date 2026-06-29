"""Human-handoff guardrail: decide when the bot should stop and escalate.

A production support bot must know its limits. This module is a deterministic
detector that fires on three signals, in priority order:

1. **Explicit request** — the customer asks for a human/agent/manager.
2. **Frustration** — angry/abusive language or repeated exasperation.
3. **Repeated failure** — the bot's tools have errored several times this
   conversation, so it's clearly stuck.

Keeping it rule-based (not another LLM call) makes it cheap, auditable, and
testable, and means the handoff still works even if the model misbehaves.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_HUMAN_REQUEST = re.compile(
    r"\b(speak|talk|connect|transfer|escalate)\b.*\b(human|agent|person|representative|"
    r"rep|someone|somebody|manager|supervisor)\b"
    r"|\b(human|real person|live agent|customer service rep|a manager|your manager)\b",
    re.IGNORECASE,
)
_FRUSTRATION = {
    "angry", "furious", "useless", "ridiculous", "terrible", "worst", "awful",
    "frustrated", "frustrating", "fed up", "unacceptable", "horrible", "disgusting",
    "scam", "garbage", "pathetic", "infuriating", "outrageous",
}


@dataclass
class EscalationDecision:
    escalate: bool
    category: str = "none"     # explicit_request | frustration | repeated_failure | none
    reason: str = ""

    @property
    def priority(self) -> str:
        return "high" if self.category in ("frustration", "repeated_failure") else "normal"


def detect_escalation(
    user_text: str,
    recent_tool_failures: int = 0,
    failure_threshold: int = 2,
) -> EscalationDecision:
    """Return whether (and why) the conversation should hand off to a human."""
    text = user_text.lower()

    if _HUMAN_REQUEST.search(user_text):
        return EscalationDecision(True, "explicit_request",
                                  "Customer explicitly asked for a human agent.")

    words = set(re.findall(r"[a-z']+", text))
    hit = words & _FRUSTRATION
    exclamations = user_text.count("!")
    shouting = len(user_text) >= 12 and sum(c.isupper() for c in user_text) / max(
        1, sum(c.isalpha() for c in user_text)) > 0.6
    if hit or exclamations >= 3 or shouting:
        why = (f"Frustration signals: {sorted(hit)}" if hit
               else "Frustration signals: emphatic/shouting tone")
        return EscalationDecision(True, "frustration", why)

    if recent_tool_failures >= failure_threshold:
        return EscalationDecision(
            True, "repeated_failure",
            f"{recent_tool_failures} tool failures this conversation — bot is stuck.")

    return EscalationDecision(False)
