"""SQLite persistence layer for the Order Service."""
import sqlite3
from contextlib import contextmanager
from typing import Iterator, List, Optional

from .models import Product


DB_PATH = "orders.db"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


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
