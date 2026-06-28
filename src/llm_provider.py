"""Pluggable function-calling providers.

A provider's job is one *step*: given the conversation so far, decide whether to
call a tool or to answer in natural language.

* :class:`MockProvider` — deterministic, offline intent router + verbalizer. No
  API key. Demonstrates the full function-calling loop in tests/CI.
* :class:`GeminiProvider` — Google Gemini native function calling.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .config import Settings, get_settings
from .tools import TOOLS

ORDER_RE = re.compile(r"\bORD[- ]?(\d{3,})\b", re.IGNORECASE)

SYSTEM_PROMPT = (
    "You are a helpful customer-support assistant for an online tea & coffee store. "
    "Use the provided tools to look up orders, products, and policies, and to start "
    "returns. Only access a customer's data after they provide their account email. "
    "Be concise and friendly. If a request is outside store support, politely decline."
)


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class ProviderResponse:
    text: str | None = None
    tool_call: ToolCall | None = None


class SupportProvider(ABC):
    @abstractmethod
    def step(self, messages: list[dict]) -> ProviderResponse:
        """Given the transcript, return either a tool call or a text answer."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...


# --- mock (offline) ---------------------------------------------------------
def _normalize_order_id(text: str) -> str | None:
    m = ORDER_RE.search(text)
    return f"ORD-{m.group(1)}" if m else None


def verbalize(name: str, result: dict) -> str:
    """Turn a tool result dict into a friendly sentence."""
    if "error" in result:
        return result["error"]
    if name == "get_order_status":
        eta = f", ETA {result['eta']}" if result.get("eta") else ""
        return f"Order {result['order_id']} is **{result['status']}** ({result['qty']}x {result['sku']}{eta})."
    if name == "list_my_orders":
        if not result["orders"]:
            return "You don't have any orders on file."
        lines = [f"- {o['order_id']}: {o['status']} ({o['sku']})" for o in result["orders"]]
        return "Here are your orders:\n" + "\n".join(lines)
    if name == "start_return":
        return (
            f"Your return **{result['return_id']}** for {result['order_id']} has been "
            f"requested. You'll get return instructions by email."
        )
    if name == "cancel_order":
        if result.get("note"):
            return f"Order {result['order_id']} is already cancelled."
        return (
            f"Order **{result['order_id']}** has been cancelled and a refund has been "
            f"{result.get('refund', 'initiated')}."
        )
    if name == "get_product_info":
        lines = [f"- {m['name']} ({m['sku']}): ${m['price']:.2f}, {m['stock']} in stock"
                 for m in result["matches"]]
        return "Here's what I found:\n" + "\n".join(lines)
    if name == "get_return_policy":
        return result["policy"]
    return str(result)


class MockProvider(SupportProvider):
    """Rule-based intent router — deterministic, key-free."""

    @property
    def name(self) -> str:
        return "mock"

    def step(self, messages: list[dict]) -> ProviderResponse:
        last = messages[-1]
        if last["role"] == "tool":
            return ProviderResponse(text=verbalize(last["name"], last["result"]))

        text = last["content"]
        low = text.lower()
        order_id = _normalize_order_id(text)

        if "return policy" in low or (("policy" in low) and "return" in low):
            return ProviderResponse(tool_call=ToolCall("get_return_policy", {}))
        if "cancel" in low and order_id:
            return ProviderResponse(tool_call=ToolCall("cancel_order", {"order_id": order_id}))
        if "return" in low and order_id:
            reason = "customer requested" if "because" not in low else low.split("because", 1)[1].strip()
            return ProviderResponse(tool_call=ToolCall("start_return", {"order_id": order_id, "reason": reason}))
        if order_id and any(w in low for w in ("status", "where", "track", "order", "delivery", "eta", "arrive")):
            return ProviderResponse(tool_call=ToolCall("get_order_status", {"order_id": order_id}))
        if "my orders" in low or "list" in low and "order" in low or low.strip() in ("orders", "my orders"):
            return ProviderResponse(tool_call=ToolCall("list_my_orders", {}))
        if any(w in low for w in ("price", "stock", "cost", "available", "how much")):
            query = _guess_product(low)
            return ProviderResponse(tool_call=ToolCall("get_product_info", {"query": query}))
        if order_id:
            return ProviderResponse(tool_call=ToolCall("get_order_status", {"order_id": order_id}))

        return ProviderResponse(
            text=(
                "I can help with order status, returns, product info, and our return policy. "
                "Try: \"What's the status of ORD-1002?\" or \"What's your return policy?\""
            )
        )


PRODUCT_HINTS = {"tea": "Tea", "coffee": "Coffee", "mug": "Mug", "kettle": "Kettle"}


def _guess_product(low: str) -> str:
    for hint, query in PRODUCT_HINTS.items():
        if hint in low:
            return query
    return low.replace("price", "").replace("stock", "").strip() or "tea"


# --- gemini -----------------------------------------------------------------
class GeminiProvider(SupportProvider):
    """Google Gemini native function calling."""

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for the Gemini provider")
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        function_declarations = [
            {"name": s.name, "description": s.description, "parameters": s.parameters}
            for s in TOOLS.values()
        ]
        self._model = genai.GenerativeModel(
            model, tools=[{"function_declarations": function_declarations}],
            system_instruction=SYSTEM_PROMPT,
        )
        self._model_name = model

    @property
    def name(self) -> str:
        return self._model_name

    def step(self, messages: list[dict]) -> ProviderResponse:
        contents = self._to_gemini_contents(messages)
        response = self._model.generate_content(contents)
        part = response.candidates[0].content.parts[0]
        fc = getattr(part, "function_call", None)
        if fc and fc.name:
            return ProviderResponse(tool_call=ToolCall(fc.name, dict(fc.args)))
        return ProviderResponse(text=(response.text or "").strip())

    @staticmethod
    def _to_gemini_contents(messages: list[dict]) -> list[dict]:
        contents = []
        for m in messages:
            if m["role"] == "user":
                contents.append({"role": "user", "parts": [m["content"]]})
            elif m["role"] == "assistant":
                contents.append({"role": "model", "parts": [m["content"]]})
            elif m["role"] == "tool":
                contents.append({
                    "role": "function",
                    "parts": [{"function_response": {"name": m["name"], "response": m["result"]}}],
                })
        return contents


def get_provider(settings: Settings | None = None) -> SupportProvider:
    settings = settings or get_settings()
    if settings.llm_provider.lower() == "mock":
        return MockProvider()
    if settings.llm_provider.lower() == "gemini":
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")
