"""Domain models for the Order Service.

These are plain dataclasses — no framework coupling, no vulnerabilities.
They exist so the demo app has actual shape for the scanners to move
through, rather than a single file of horrors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"


@dataclass
class Product:
    id: int
    sku: str
    name: str
    price_cents: int
    stock: int
    category: str = "general"

    def is_in_stock(self, qty: int = 1) -> bool:
        return self.stock >= qty


@dataclass
class User:
    id: int
    email: str
    password_hash: str
    is_admin: bool = False


@dataclass
class OrderItem:
    product_id: int
    sku: str
    quantity: int
    unit_price_cents: int

    @property
    def line_total_cents(self) -> int:
        return self.quantity * self.unit_price_cents


@dataclass
class Order:
    id: int
    user_id: int
    items: List[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PENDING
    coupon_code: str | None = None
    discount_cents: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def subtotal_cents(self) -> int:
        return sum(item.line_total_cents for item in self.items)

    @property
    def total_cents(self) -> int:
        return max(0, self.subtotal_cents - self.discount_cents)
