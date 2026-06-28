from src.tools import ToolContext, execute_tool, get_order_status, start_return


def test_get_order_status_found(settings):
    ctx = ToolContext(db_path=settings.db_path, email="alice@example.com")
    res = get_order_status(ctx, "ORD-1002")
    assert res["status"] == "shipped"


def test_get_order_status_wrong_account_blocked(settings):
    ctx = ToolContext(db_path=settings.db_path, email="bob@example.com")
    res = get_order_status(ctx, "ORD-1002")  # belongs to alice
    assert "error" in res and "different account" in res["error"]


def test_start_return_only_for_delivered(settings):
    ctx = ToolContext(db_path=settings.db_path, email="alice@example.com")
    ok = start_return(ctx, "ORD-1001", reason="damaged")  # delivered
    assert ok["status"] == "requested" and ok["return_id"].startswith("RET-")

    bad = start_return(ctx, "ORD-1002", reason="x")  # shipped, not delivered
    assert "error" in bad


def test_list_my_orders_requires_auth(settings):
    ctx = ToolContext(db_path=settings.db_path, email=None)
    res = execute_tool("list_my_orders", ctx, {})
    assert "error" in res

    ctx.email = "alice@example.com"
    res2 = execute_tool("list_my_orders", ctx, {})
    assert len(res2["orders"]) == 2


def test_get_product_info(settings):
    ctx = ToolContext(db_path=settings.db_path)
    res = execute_tool("get_product_info", ctx, {"query": "kettle"})
    assert res["matches"][0]["sku"] == "SKU-KET"


def test_unknown_tool(settings):
    ctx = ToolContext(db_path=settings.db_path)
    assert "error" in execute_tool("does_not_exist", ctx, {})
