from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# -----------------------------
# Base (shared fields)
# -----------------------------
class OrderLineItemBase(BaseModel):
    order_id: str = Field(..., description="UUID of the parent Order")
    ticket_type_id: str = Field(..., description="UUID of the TicketType")
    quantity: int = Field(..., ge=1, description="Quantity (must be >= 1)")
    # NOTE: DB also enforces a unique (order_id, ticket_type_id) pair.


# -----------------------------
# Create (POST)
# -----------------------------
class OrderLineItemCreate(OrderLineItemBase):
    """Payload for creating an OrderLineItem."""
    pass


# -----------------------------
# Replace (PUT)
# -----------------------------
class OrderLineItemPut(OrderLineItemBase):
    """Full replacement (except id)."""
    pass


# -----------------------------
# Patch (PATCH)
# -----------------------------
class OrderLineItemPatch(BaseModel):
    """Partial update; all fields optional."""
    order_id: Optional[str] = None
    ticket_type_id: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=1)


# -----------------------------
# Read (GET responses)
# -----------------------------
class OrderLineItemRead(OrderLineItemBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Allow constructing from ORM objects
    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# Back-compat export aliases
# -----------------------------
OrderLineItemOut = OrderLineItemRead        # response schema
OrderLineItemIn = OrderLineItemCreate       # create schema
OrderLineItemUpdate = OrderLineItemPatch    # patch schema
OrderLineItemReplace = OrderLineItemPut     # put schema

__all__ = [
    "OrderLineItemBase",
    "OrderLineItemCreate",
    "OrderLineItemPut",
    "OrderLineItemPatch",
    "OrderLineItemRead",
    # legacy names:
    "OrderLineItemOut",
    "OrderLineItemIn",
    "OrderLineItemUpdate",
    "OrderLineItemReplace",
]
