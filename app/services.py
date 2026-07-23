"""Order and pricing business logic.

This module holds the "how does an order work" logic — validation, pricing,
discount application, state transitions. Kept intentionally clean so scanners
have a mix of vulnerable and non-vulnerable code to move through, which is
what a real codebase looks like.
"""
from __future__ import annotations

from typing import Dict, Iterable, Tuple

from .models import Order, OrderItem, OrderStatus, Product


# Coupon table — in a real app this would live in the DB.
COUPONS: Dict[str, Tuple[str, int]] = {
    "WELCOME10": ("percent", 10),   # 10% off
    "SAVE5":     ("flat",    500),  # $5 off
    "SHIP0":     ("flat",    999),  # ~$10 off shipping proxy
}

TAX_RATES: Dict[str, float] = {
    "US": 0.0725,
    "CA": 0.13,
    "UK": 0.20,
    "DE": 0.19,
}


def build_order(
    order_id: int,
    user_id: int,
    cart: Iterable[Tuple[Product, int]],
) -> Order:
    """Build an Order from a cart of (product, quantity) tuples.

    Raises ValueError if any product is out of stock at the requested qty.
    """
    items = []
    for product, qty in cart:
        if not product.is_in_stock(qty):
            raise ValueError(f"SKU {product.sku} is short of stock: need {qty}, have {product.stock}")
        items.append(
            OrderItem(
                product_id=product.id,
                sku=product.sku,
                quantity=qty,
                unit_price_cents=product.price_cents,
            )
        )
    return Order(id=order_id, user_id=user_id, items=items)


def apply_coupon(order: Order, code: str) -> Order:
    """Apply a coupon to an order. Unknown codes are silently ignored."""
    if code not in COUPONS:
        return order
    kind, value = COUPONS[code]
    if kind == "percent":
        order.discount_cents = order.subtotal_cents * value // 100
    elif kind == "flat":
        order.discount_cents = min(value, order.subtotal_cents)
    order.coupon_code = code
    return order


def calculate_tax_cents(order: Order, country_code: str) -> int:
    """Compute tax owed on an order for a given country."""
    rate = TAX_RATES.get(country_code.upper(), 0.0)
    return int(order.total_cents * rate)


def mark_paid(order: Order) -> Order:
    _require_status(order, OrderStatus.PENDING)
    order.status = OrderStatus.PAID
    return order


def mark_shipped(order: Order) -> Order:
    _require_status(order, OrderStatus.PAID)
    order.status = OrderStatus.SHIPPED
    return order


def cancel(order: Order) -> Order:
    if order.status == OrderStatus.SHIPPED:
        raise ValueError("Cannot cancel an already-shipped order")
    order.status = OrderStatus.CANCELLED
    return order


def _require_status(order: Order, expected: OrderStatus) -> None:
    if order.status != expected:
        raise ValueError(f"Order {order.id} is {order.status}, expected {expected}")
