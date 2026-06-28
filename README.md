# 🛍️ LLM Customer-Support Chatbot with Function Calling

A support assistant for a fictional tea & coffee store that **answers FAQs and takes real actions** — checking order status, listing a customer's orders, starting returns, and looking up products — by calling functions against a SQLite backend. Includes conversation memory and identity guardrails.

> This is the "LLM that actually *does* things" pattern clients ask for: not just chat, but tool-use against your systems, safely.

---

## What it does / who it's for

Most support volume is repetitive: *"Where's my order?"*, *"How do I return this?"*, *"Is X in stock?"*. This bot resolves those end-to-end by combining natural-language understanding with **function calling** into a real (mock) backend — deflecting tickets while staying safe (a customer can only see their own data).

## Key capabilities (what it proves)

- **Function calling loop:** the model chooses a tool, the app executes it, the result is fed back, and the model replies — fully orchestrated.
- **Real actions, not just answers:** `get_order_status`, `list_my_orders`, `start_return`, `get_product_info`, `get_return_policy` against SQLite.
- **Conversation memory:** identity captured once is reused across turns.
- **Guardrails:** personal-data tools require a verified email; cross-account access is blocked; returns enforce the policy window.
- **Pluggable provider:** Google **Gemini** native function calling in production; a deterministic **offline mock** router for tests/CI/demos (no key).
- **Two interfaces:** FastAPI `/chat` (per-session memory) and a Streamlit chat UI.

## Demo

Real transcript (offline mock provider):

```text
USER: Hi! My email is alice@example.com
BOT : Thanks — I've verified your account (alice@example.com)...

USER: What's the status of ORD-1002?
BOT : Order ORD-1002 is shipped (1x SKU-KET, ETA 2026-06-30).      [tool: get_order_status]

USER: List my orders
BOT : Here are your orders:
      - ORD-1002: shipped (SKU-KET)
      - ORD-1001: delivered (SKU-TEA)                              [tool: list_my_orders]

USER: I'd like to return ORD-1001 because it arrived damaged
BOT : Your return RET-6F68C9 for ORD-1001 has been requested...    [tool: start_return]

USER: What's your return policy?
BOT : Items can be returned within 30 days of delivery...          [tool: get_return_policy]
```

**Guardrail in action** — a customer can't read another account's order:

```text
USER: my email is bob@example.com
USER: status of ORD-1002          (this order belongs to Alice)
BOT : This order belongs to a different account.
```

**API:**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "s1", "message": "status of ORD-1003, my email is bob@example.com"}'
```

## How it works

```
user turn ─► capture identity (email) ─► [agent loop, ≤ MAX_TOOL_STEPS]
                                              │
                                  provider.step(transcript)
                                       │            │
                                  tool_call?    text answer ──► reply
                                       │
                              execute_tool() ──► append result ──► loop again
```

The provider only decides *what to do next*; the agent executes tools and keeps the transcript (memory). Swapping `mock` ↔ `gemini` changes nothing else.

## Tech stack

- **API:** FastAPI, Uvicorn, Pydantic
- **Backend:** SQLite (customers / products / orders / returns)
- **LLM:** Google Gemini function calling (`google-generativeai`), pluggable
- **UI:** Streamlit chat
- **Tests:** pytest (12 tests covering tools, guardrails, and the agent loop)

## Setup & run

```bash
cd 04-llm-support-chatbot
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # works offline, no key needed

python -m src.generate_data     # seed the mock store DB
uvicorn api:app --reload        # API at http://localhost:8000/docs
streamlit run app.py            # chat UI
pytest -q
```

Enable Gemini in `.env`: `LLM_PROVIDER=gemini` and `GEMINI_API_KEY=...`.

## Project structure

```
04-llm-support-chatbot/
├── api.py                  # FastAPI /chat with per-session memory
├── app.py                  # Streamlit chat UI
├── src/
│   ├── config.py           # settings from .env
│   ├── database.py         # SQLite schema + connection
│   ├── generate_data.py    # seed customers/products/orders
│   ├── tools.py            # callable tools + JSON schemas + guardrails
│   ├── guardrails.py       # identity capture, input hygiene
│   ├── llm_provider.py     # Gemini function calling + offline mock router
│   └── agent.py            # function-calling loop + conversation memory
├── tests/                  # 12 pytest tests
├── requirements.txt
├── .env.example
└── .gitignore
```

## Possible extensions

- **RAG over a help center** for open-ended FAQs (combine with project 01).
- **Human handoff** when confidence is low or the request is out of scope.
- **Auth** via real session tokens / OTP instead of email capture.
- **More tools:** address changes, cancellations, refunds, shipment tracking webhooks.
- **Analytics:** deflection rate, tool success rate, escalation reasons.
