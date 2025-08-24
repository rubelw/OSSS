# src/OSSS/schemas/orders.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal, Dict, Any

from pydantic import Field
from .base import ORMBase

OrderStatus = Literal["pending", "paid", "cancelled", "refunded"]


class OrderBase(ORMBase):
    event_id: str
    purchaser_user_id: Optional[str] = None
    # store money as cents to avoid float issues
    total_cents: int = Field(0, ge=0)
    currency: str = Field("USD", min_length=3, max_length=8)
    status: OrderStatus = "pending"
    external_ref: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class OrderCreate(OrderBase):
    """Payload for creating a new order."""
    # event_id is required via OrderBase; everything else has sensible defaults/optionals
    pass


# Useful alias if your routers expect `OrderIn`
OrderIn = OrderCreate


class OrderUpdate(ORMBase):
    """Partial update; all fields optional."""
    purchaser_user_id: Optional[str] = None
    total_cents: Optional[int] = Field(None, ge=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=8)
    status: Optional[OrderStatus] = None
    external_ref: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class OrderOut(OrderBase):
    id: str
    created_at: datetime
    updated_at: datetime
