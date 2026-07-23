"""SQLite persistence layer for the Order Service."""
import sqlite3
from contextlib import contextmanager
from typing import Iterator, List, Optional

from .models import Order, Product


DB_PATH = "orders.db"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they do not already exist."""
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                sku         TEXT    NOT NULL UNIQUE,
                name        TEXT    NOT NULL,
                price_cents INTEGER NOT NULL,
                stock       INTEGER NOT NULL DEFAULT 0,
                category    TEXT    NOT NULL DEFAULT 'general'
            );

            CREATE TABLE IF NOT EXISTS orders (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL,
                coupon_code    TEXT,
                discount_cents INTEGER NOT NULL DEFAULT 0,
                status         TEXT    NOT NULL DEFAULT 'pending',
                created_at     TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id        INTEGER NOT NULL REFERENCES orders(id),
                product_id      INTEGER NOT NULL REFERENCES products(id),
                sku             TEXT    NOT NULL,
                quantity        INTEGER NOT NULL,
                unit_price_cents INTEGER NOT NULL
            );
            """
        )


def insert_order(order: Order) -> int:
    """Persist an order and its line items; return the generated order ID."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO orders (user_id, coupon_code, discount_cents, status, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                order.user_id,
                order.coupon_code,
                order.discount_cents,
                order.status.value,
                order.created_at.isoformat(),
            ),
        )
        order_id = cursor.lastrowid
        cursor.executemany(
            "INSERT INTO order_items (order_id, product_id, sku, quantity, unit_price_cents) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (order_id, item.product_id, item.sku, item.quantity, item.unit_price_cents)
                for item in order.items
            ],
        )
        return order_id


def list_products(category: Optional[str] = None) -> List[Product]:
    """List products, optionally filtered by category."""
    with connect() as conn:
        cursor = conn.cursor()
        if category:
            cursor.execute(
                "SELECT id, sku, name, price_cents, stock, category "
                "FROM products WHERE category = ?",
                (category,),
            )
        else:
            cursor.execute(
                "SELECT id, sku, name, price_cents, stock, category FROM products"
            )
        return [
            Product(id=r[0], sku=r[1], name=r[2], price_cents=r[3], stock=r[4], category=r[5])
            for r in cursor.fetchall()
        ]


def find_product_by_sku(sku: str) -> Optional[Product]:
    """Look up a single product by SKU."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, sku, name, price_cents, stock, category FROM products WHERE sku = ?",
            (sku,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return Product(id=row[0], sku=row[1], name=row[2], price_cents=row[3], stock=row[4], category=row[5])


def decrement_stock(product_id: int, qty: int) -> None:
    """Decrement stock atomically after a successful order."""
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?",
            (qty, product_id, qty),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"Failed to decrement stock for product {product_id}")
