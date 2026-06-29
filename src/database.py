"""SQLite mock e-commerce backend.

Schema: customers, products, orders, returns. All access goes through this thin
data layer so the tools stay business-logic-only.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    email TEXT PRIMARY KEY,
    name  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    sku   TEXT PRIMARY KEY,
    name  TEXT NOT NULL,
    price REAL NOT NULL,
    stock INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    order_id   TEXT PRIMARY KEY,
    email      TEXT NOT NULL,
    sku        TEXT NOT NULL,
    qty        INTEGER NOT NULL,
    status     TEXT NOT NULL,          -- placed | shipped | delivered | cancelled
    order_date TEXT NOT NULL,
    eta        TEXT,
    FOREIGN KEY (email) REFERENCES customers(email),
    FOREIGN KEY (sku)   REFERENCES products(sku)
);
CREATE TABLE IF NOT EXISTS returns (
    return_id  TEXT PRIMARY KEY,
    order_id   TEXT NOT NULL,
    reason     TEXT,
    status     TEXT NOT NULL,          -- requested | approved | completed
    created_at TEXT NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);
CREATE TABLE IF NOT EXISTS support_tickets (
    ticket_id  TEXT PRIMARY KEY,
    email      TEXT,                   -- may be null if not yet identified
    category   TEXT NOT NULL,          -- explicit_request | frustration | repeated_failure | general
    priority   TEXT NOT NULL,          -- normal | high
    reason     TEXT,
    status     TEXT NOT NULL,          -- open | resolved
    created_at TEXT NOT NULL
);
"""


@contextmanager
def connect(db_path: str):
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def reset_db(db_path: str) -> None:
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(db_path)
