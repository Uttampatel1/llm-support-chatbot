"""The support agent: orchestrates the function-calling loop with memory.

Flow per user turn:
1. Capture identity (email) if present  -> guardrail for personal-data tools.
2. Ask the provider for the next step (tool call or answer).
3. If a tool is requested, execute it, append the result, and ask again.
4. Stop at a natural-language answer (or after MAX_TOOL_STEPS).

The full transcript (including tool calls and results) is retained as memory and
returned for transparency.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import Settings, get_settings
from .escalation import detect_escalation
from .guardrails import customer_exists, extract_email, sanitize_input
from .llm_provider import SupportProvider, get_provider
from .logging_utils import get_logger
from .tools import ToolContext, execute_tool

log = get_logger(__name__)


@dataclass
class TurnResult:
    reply: str
    tool_calls: list[dict] = field(default_factory=list)
    authenticated_as: str | None = None
    escalated: bool = False
    ticket_id: str | None = None


class SupportAgent:
    def __init__(self, settings: Settings | None = None, provider: SupportProvider | None = None):
        self.settings = settings or get_settings()
        self.provider = provider or get_provider(self.settings)
        self.ctx = ToolContext(db_path=self.settings.db_path)
        self.transcript: list[dict] = []
        self._tool_failures = 0  # cumulative across the conversation

    def _capture_identity(self, text: str) -> str | None:
        email = extract_email(text)
        if email and customer_exists(self.ctx.db_path, email):
            self.ctx.email = email
            return f"Thanks — I've verified your account ({email}). "
        if email and not customer_exists(self.ctx.db_path, email):
            return "I couldn't find an account with that email. "
        return None

    def _escalate(self, category: str, reason: str, prefix: str, tool_calls: list[dict]) -> TurnResult:
        """Open a human-handoff ticket and return a closing reply for this turn."""
        info = execute_tool("escalate_to_human", self.ctx, {"reason": reason, "category": category})
        tool_calls.append({"name": "escalate_to_human", "args": {"reason": reason, "category": category},
                           "result": info})
        log.info("escalated (%s) -> ticket %s", category, info.get("ticket_id"))
        reply = (
            f"{prefix}I'm connecting you with a human specialist who can help further. "
            f"I've opened ticket **{info['ticket_id']}** (priority: {info['priority']}) and a support "
            "agent will follow up shortly. Is there anything else I can note for them?"
        )
        self.transcript.append({"role": "assistant", "content": reply})
        return TurnResult(reply=reply, tool_calls=tool_calls, authenticated_as=self.ctx.email,
                          escalated=True, ticket_id=info["ticket_id"])

    def chat(self, user_text: str) -> TurnResult:
        user_text = sanitize_input(user_text)
        prefix = self._capture_identity(user_text) or ""
        self.transcript.append({"role": "user", "content": user_text})

        tool_calls: list[dict] = []

        # Guardrail: hand off to a human on explicit request, frustration, or
        # after repeated tool failures earlier in the conversation.
        if self.settings.escalation_enabled:
            decision = detect_escalation(
                user_text, self._tool_failures, self.settings.escalation_failure_threshold)
            if decision.escalate:
                return self._escalate(decision.category, decision.reason, prefix, tool_calls)

        for _ in range(self.settings.max_tool_steps):
            resp = self.provider.step(self.transcript)
            if resp.tool_call is not None:
                result = execute_tool(resp.tool_call.name, self.ctx, resp.tool_call.args)
                if "error" in result:
                    self._tool_failures += 1
                log.info("tool_call %s(%s) -> %s", resp.tool_call.name, resp.tool_call.args,
                         "error" if "error" in result else "ok")
                tool_calls.append({"name": resp.tool_call.name, "args": resp.tool_call.args, "result": result})
                self.transcript.append({"role": "tool", "name": resp.tool_call.name, "result": result})
                # Stuck on repeated failures? Escalate instead of looping uselessly.
                if (self.settings.escalation_enabled
                        and self._tool_failures >= self.settings.escalation_failure_threshold):
                    return self._escalate(
                        "repeated_failure",
                        f"{self._tool_failures} tool failures this conversation.",
                        prefix, tool_calls)
                continue
            reply = prefix + (resp.text or "")
            self.transcript.append({"role": "assistant", "content": reply})
            return TurnResult(reply=reply, tool_calls=tool_calls, authenticated_as=self.ctx.email)

        # Safety net if the loop didn't converge.
        fallback = prefix + "Sorry, I couldn't complete that — could you rephrase?"
        self.transcript.append({"role": "assistant", "content": fallback})
        return TurnResult(reply=fallback, tool_calls=tool_calls, authenticated_as=self.ctx.email)
