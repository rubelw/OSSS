"""
Pydantic schemas for StoreOrder

Follows the same style/pattern as other schemas in `src/OSSS/schemas`.
Backed by model defined in `db/models/store_orders.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr

# Import the SQLAlchemy enum to keep values aligned with the model
try:
    # If the enum is exported alongside the model
    from OSSS.db.models.store_orders import OrderStatus  # type: ignore
except Exception:
    # Fallback: a minimal compatible Enum to avoid import issues in type checking contexts
    # (Your runtime should use the real enum from the model.)
    from enum import Enum

    class OrderStatus(str, Enum):  # type: ignore[no-redef]
        pending = "pending"
        paid = "paid"
        fulfilled = "fulfilled"
        cancelled = "cancelled"


# ---- Base ----
class StoreOrderBase(BaseModel):
    """Shared fields between create/read/update for a StoreOrder record."""

    buyer_name: Optional[str] = Field(
        default=None, description="Customer's display name (optional)."
    )
    buyer_email: Optional[EmailStr] = Field(
        default=None, description="Customer email (optional)."
    )
    total_cents: Optional[int] = Field(
        default=None,
        ge=0,
        description="Computed order total in integer cents (server-calculated; may be null before items).",
    )
    status: OrderStatus = Field(
        default=OrderStatus.pending,
        description="Order status lifecycle value.",
    )


# ---- Create ----
class StoreOrderCreate(StoreOrderBase):
    """Payload for creating a new StoreOrder."""

    school_id: UUID = Field(description="FK to the associated school.")


# ---- Update (PATCH) ----
class StoreOrderUpdate(BaseModel):
    """Partial update for an existing StoreOrder."""

    buyer_name: Optional[str] = None
    buyer_email: Optional[EmailStr] = None
    total_cents: Optional[int] = Field(default=None, ge=0)
    status: Optional[OrderStatus] = None
    school_id: Optional[UUID] = None


# ---- Read ----
class StoreOrderRead(StoreOrderBase):
    """Replica of a persisted StoreOrder (as returned by the API)."""

    id: UUID
    school_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Pydantic v2: allow construction from ORM objects
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


# ---- Lightweight summaries / lists ----
class StoreOrderSummary(BaseModel):
    """Minimal listing view of store orders for tables or dropdowns."""

    id: UUID
    school_id: UUID
    buyer_name: Optional[str] = None
    status: OrderStatus
    total_cents: Optional[int] = None

    model_config = {"from_attributes": True}


class StoreOrderList(BaseModel):
    """Container useful for list endpoints that wrap results (kept optional)."""

    items: list[StoreOrderSummary]
    total: int = Field(description="Total matching records (for pagination).")
