"""Seed the mock store database with synthetic customers, products, orders.

Run:  python -m src.generate_data
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .config import get_settings
from .database import connect, reset_db

CUSTOMERS = [
    ("alice@example.com", "Alice Kumar"),
    ("bob@example.com", "Bob Sharma"),
    ("carol@example.com", "Carol Mehta"),
]

PRODUCTS = [
    ("SKU-TEA", "Assam Black Tea (250g)", 12.50, 120),
    ("SKU-COF", "Arabica Coffee Beans (500g)", 19.00, 80),
    ("SKU-MUG", "Ceramic Mug", 8.00, 200),
    ("SKU-KET", "Electric Kettle", 34.00, 15),
]

# (order_id, email, sku, qty, status, days_ago, eta_days)
ORDERS = [
    ("ORD-1001", "alice@example.com", "SKU-TEA", 2, "delivered", 12, -5),
    ("ORD-1002", "alice@example.com", "SKU-KET", 1, "shipped", 3, 2),
    ("ORD-1003", "bob@example.com", "SKU-COF", 3, "placed", 1, 4),
    ("ORD-1004", "bob@example.com", "SKU-MUG", 4, "delivered", 20, -14),
    ("ORD-1005", "carol@example.com", "SKU-COF", 1, "cancelled", 8, None),
]


def seed(db_path: str | None = None) -> str:
    db_path = db_path or get_settings().db_path
    reset_db(db_path)
    today = datetime.now().date()
    with connect(db_path) as conn:
        conn.executemany("INSERT INTO customers VALUES (?, ?)", CUSTOMERS)
        conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", PRODUCTS)
        for oid, email, sku, qty, status, days_ago, eta_days in ORDERS:
            order_date = (today - timedelta(days=days_ago)).isoformat()
            eta = (today + timedelta(days=eta_days)).isoformat() if eta_days is not None else None
            conn.execute(
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)",
                (oid, email, sku, qty, status, order_date, eta),
            )
    return db_path


def main() -> None:
    path = seed()
    print(f"Seeded mock store at {path}")
    print(f"  {len(CUSTOMERS)} customers, {len(PRODUCTS)} products, {len(ORDERS)} orders")
    print("  Try: alice@example.com (ORD-1001 delivered, ORD-1002 shipped)")


if __name__ == "__main__":
    main()
