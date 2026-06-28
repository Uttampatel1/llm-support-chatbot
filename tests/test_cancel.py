from __future__ import annotations

from src.tools import ToolContext, cancel_order, execute_tool, get_order_status


def test_cancel_placed_order_succeeds(settings):
    ctx = ToolContext(db_path=settings.db_path, email="bob@example.com")
    res = cancel_order(ctx, "ORD-1003")  # bob's order, status 'placed'
    assert res["status"] == "cancelled"
    assert res["refund"] == "initiated"
    # The change is persisted.
    assert get_order_status(ctx, "ORD-1003")["status"] == "cancelled"


def test_cannot_cancel_shipped_order(settings):
    ctx = ToolContext(db_path=settings.db_path, email="alice@example.com")
    res = cancel_order(ctx, "ORD-1002")  # shipped
    assert "error" in res
    assert "shipped" in res["error"] or "cancelled" in res["error"]


def test_cancel_requires_authentication(settings):
    ctx = ToolContext(db_path=settings.db_path, email=None)
    res = execute_tool("cancel_order", ctx, {"order_id": "ORD-1003"})
    assert "error" in res  # requires_auth gate


def test_cannot_cancel_other_customers_order(settings):
    ctx = ToolContext(db_path=settings.db_path, email="alice@example.com")
    res = cancel_order(ctx, "ORD-1003")  # belongs to bob
    assert "error" in res and "different account" in res["error"]


def test_cancel_already_cancelled_is_idempotent(settings):
    ctx = ToolContext(db_path=settings.db_path, email="carol@example.com")
    res = cancel_order(ctx, "ORD-1005")  # already cancelled
    assert res["status"] == "cancelled"
