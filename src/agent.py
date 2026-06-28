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


class SupportAgent:
    def __init__(self, settings: Settings | None = None, provider: SupportProvider | None = None):
        self.settings = settings or get_settings()
        self.provider = provider or get_provider(self.settings)
        self.ctx = ToolContext(db_path=self.settings.db_path)
        self.transcript: list[dict] = []

    def _capture_identity(self, text: str) -> str | None:
        email = extract_email(text)
        if email and customer_exists(self.ctx.db_path, email):
            self.ctx.email = email
            return f"Thanks — I've verified your account ({email}). "
        if email and not customer_exists(self.ctx.db_path, email):
            return "I couldn't find an account with that email. "
        return None

    def chat(self, user_text: str) -> TurnResult:
        user_text = sanitize_input(user_text)
        prefix = self._capture_identity(user_text) or ""
        self.transcript.append({"role": "user", "content": user_text})

        tool_calls: list[dict] = []
        for _ in range(self.settings.max_tool_steps):
            resp = self.provider.step(self.transcript)
            if resp.tool_call is not None:
                result = execute_tool(resp.tool_call.name, self.ctx, resp.tool_call.args)
                log.info("tool_call %s(%s) -> %s", resp.tool_call.name, resp.tool_call.args,
                         "error" if "error" in result else "ok")
                tool_calls.append({"name": resp.tool_call.name, "args": resp.tool_call.args, "result": result})
                self.transcript.append({"role": "tool", "name": resp.tool_call.name, "result": result})
                continue
            reply = prefix + (resp.text or "")
            self.transcript.append({"role": "assistant", "content": reply})
            return TurnResult(reply=reply, tool_calls=tool_calls, authenticated_as=self.ctx.email)

        # Safety net if the loop didn't converge.
        fallback = prefix + "Sorry, I couldn't complete that — could you rephrase?"
        self.transcript.append({"role": "assistant", "content": fallback})
        return TurnResult(reply=fallback, tool_calls=tool_calls, authenticated_as=self.ctx.email)
