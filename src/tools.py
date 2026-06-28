"""Callable tools the assistant can invoke (function calling).

Each tool is pure business logic over the mock DB plus guardrails (e.g. a
customer can only see their *own* orders). Tools return JSON-serializable dicts.
The :data:`TOOLS` registry exposes name, description, JSON-schema parameters,
and the python callable — everything a function-calling LLM needs.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from .database import connect

RETURN_WINDOW_DAYS = 30


@dataclass
class ToolContext:
    """Per-conversation context: which DB, and who is authenticated."""

    db_path: str
    email: str | None = None  # set once the customer identifies themselves


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable[..., dict]
    requires_auth: bool = False


# --- tool implementations ---------------------------------------------------
def _order_row(db_path: str, order_id: str):
    with connect(db_path) as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id.upper(),)
        ).fetchone()


def get_order_status(ctx: ToolContext, order_id: str) -> dict:
    row = _order_row(ctx.db_path, order_id)
    if row is None:
        return {"error": f"No order found with id {order_id}."}
    if ctx.email and row["email"] != ctx.email:
        return {"error": "This order belongs to a different account."}
    return {
        "order_id": row["order_id"],
        "status": row["status"],
        "sku": row["sku"],
        "qty": row["qty"],
        "order_date": row["order_date"],
        "eta": row["eta"],
    }


def list_my_orders(ctx: ToolContext) -> dict:
    if not ctx.email:
        return {"error": "Please provide your account email first."}
    with connect(ctx.db_path) as conn:
        rows = conn.execute(
            "SELECT order_id, sku, status, order_date FROM orders WHERE email = ? ORDER BY order_date DESC",
            (ctx.email,),
        ).fetchall()
    return {"email": ctx.email, "orders": [dict(r) for r in rows]}


def start_return(ctx: ToolContext, order_id: str, reason: str = "") -> dict:
    row = _order_row(ctx.db_path, order_id)
    if row is None:
        return {"error": f"No order found with id {order_id}."}
    if ctx.email and row["email"] != ctx.email:
        return {"error": "This order belongs to a different account."}
    if row["status"] != "delivered":
        return {"error": f"Returns are only allowed for delivered orders (this is '{row['status']}')."}

    days = (datetime.now().date() - datetime.fromisoformat(row["order_date"]).date()).days
    if days > RETURN_WINDOW_DAYS:
        return {"error": f"Return window is {RETURN_WINDOW_DAYS} days; this order is {days} days old."}

    return_id = f"RET-{uuid.uuid4().hex[:6].upper()}"
    with connect(ctx.db_path) as conn:
        conn.execute(
            "INSERT INTO returns VALUES (?, ?, ?, ?, ?)",
            (return_id, row["order_id"], reason, "requested", datetime.now().isoformat()),
        )
    return {"return_id": return_id, "order_id": row["order_id"], "status": "requested", "reason": reason}


def cancel_order(ctx: ToolContext, order_id: str) -> dict:
    """Cancel an order that hasn't shipped yet (status == 'placed')."""
    row = _order_row(ctx.db_path, order_id)
    if row is None:
        return {"error": f"No order found with id {order_id}."}
    if ctx.email and row["email"] != ctx.email:
        return {"error": "This order belongs to a different account."}
    if row["status"] == "cancelled":
        return {"order_id": row["order_id"], "status": "cancelled", "note": "Already cancelled."}
    if row["status"] != "placed":
        return {
            "error": (
                f"Only orders that haven't shipped can be cancelled "
                f"(this order is '{row['status']}'). Try a return once it's delivered."
            )
        }
    with connect(ctx.db_path) as conn:
        conn.execute(
            "UPDATE orders SET status = 'cancelled' WHERE order_id = ?", (row["order_id"],)
        )
    return {"order_id": row["order_id"], "status": "cancelled", "refund": "initiated"}


def get_product_info(ctx: ToolContext, query: str) -> dict:
    with connect(ctx.db_path) as conn:
        rows = conn.execute(
            "SELECT sku, name, price, stock FROM products WHERE name LIKE ? OR sku LIKE ?",
            (f"%{query}%", f"%{query}%"),
        ).fetchall()
    if not rows:
        return {"error": f"No product matched '{query}'."}
    return {"matches": [dict(r) for r in rows]}


def get_return_policy(ctx: ToolContext) -> dict:
    return {
        "window_days": RETURN_WINDOW_DAYS,
        "policy": (
            f"Items can be returned within {RETURN_WINDOW_DAYS} days of delivery for a full "
            "refund, provided they are unused and in original packaging."
        ),
    }


# --- registry ---------------------------------------------------------------
TOOLS: dict[str, ToolSpec] = {
    "get_order_status": ToolSpec(
        name="get_order_status",
        description="Get the current status, ETA and details of a specific order by its order id.",
        parameters={
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "Order id, e.g. ORD-1002"}},
            "required": ["order_id"],
        },
        func=get_order_status,
    ),
    "list_my_orders": ToolSpec(
        name="list_my_orders",
        description="List all orders belonging to the authenticated customer.",
        parameters={"type": "object", "properties": {}},
        func=list_my_orders,
        requires_auth=True,
    ),
    "start_return": ToolSpec(
        name="start_return",
        description="Start a return for a delivered order within the return window.",
        parameters={
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order id to return"},
                "reason": {"type": "string", "description": "Reason for the return"},
            },
            "required": ["order_id"],
        },
        func=start_return,
        requires_auth=False,
    ),
    "cancel_order": ToolSpec(
        name="cancel_order",
        description="Cancel an order that has not shipped yet. Requires the customer to be authenticated.",
        parameters={
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "Order id to cancel"}},
            "required": ["order_id"],
        },
        func=cancel_order,
        requires_auth=True,
    ),
    "get_product_info": ToolSpec(
        name="get_product_info",
        description="Look up product price and stock by name or SKU.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Product name or SKU"}},
            "required": ["query"],
        },
        func=get_product_info,
    ),
    "get_return_policy": ToolSpec(
        name="get_return_policy",
        description="Explain the store's return policy and window.",
        parameters={"type": "object", "properties": {}},
        func=get_return_policy,
    ),
}


def execute_tool(name: str, ctx: ToolContext, args: dict) -> dict:
    spec = TOOLS.get(name)
    if spec is None:
        return {"error": f"Unknown tool: {name}"}
    if spec.requires_auth and not ctx.email:
        return {"error": "Please provide your account email so I can verify your identity."}
    try:
        return spec.func(ctx, **args)
    except TypeError as exc:
        return {"error": f"Invalid arguments for {name}: {exc}"}
