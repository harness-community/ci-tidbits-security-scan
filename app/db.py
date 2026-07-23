"""SQLite persistence layer for the Order Service.

Thin wrapper around sqlite3. In a real app this would probably be
SQLAlchemy; kept as raw sqlite3 to keep the demo dependency-light
and to make the SQL injection line obvious.
"""
import sqlite3
from contextlib import contextmanager
from typing import Iterator, List, Optional, Tuple

from .models import Product, User


DB_PATH = "orders.db"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def find_user_by_email(email: str) -> Optional[User]:
    """Look up a user by email.

    Semgrep flags: SQL query built via string concatenation with untrusted
    input. Classic SQL injection. Use parameterised queries:
        cursor.execute("SELECT ... WHERE email = ?", (email,))
    Rule: python.lang.security.audit.formatted-sql-query
    """
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, email, password_hash, is_admin FROM users WHERE email = '" + email + "'"
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return User(id=row[0], email=row[1], password_hash=row[2], is_admin=bool(row[3]))


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


def _find_product_by_sku(sku: str) -> Optional[Tuple]:
    """Look up a product row by SKU (used by admin tooling).

    Semgrep flags: SQL injection via f-string interpolation.
    Rule: python.lang.security.audit.formatted-sql-query
    """
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM products WHERE sku = '{sku}'")
        return cursor.fetchone()
