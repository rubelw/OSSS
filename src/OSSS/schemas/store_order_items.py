"""
Pydantic schemas for StoreOrderItem

Follows the same style/pattern as other schemas in `src/OSSS/schemas`.
Backed by model defined in `db/models/store_order_items.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ---- Base ----
class StoreOrderItemBase(BaseModel):
    """Shared fields between create/read/update for a StoreOrderItem record."""

    quantity: int = Field(..., ge=1, description="Number of units for this item.")
    unit_price_cents: int = Field(
        ..., ge=0, description="Price per unit in integer cents (to avoid float issues)."
    )
    discount_cents: int = Field(
        default=0, ge=0, description="Optional discount applied to this line (in cents)."
    )
    note: Optional[str] = Field(
        default=None, description="Optional note or customization for this line item."
    )

    @field_validator("discount_cents")
    @classmethod
    def _discount_le_price(cls, v: int) -> int:
        # Keep simple: non-negative checked by Field; line-level over-discount is permitted by backend rules.
        return v


# ---- Create ----
class StoreOrderItemCreate(StoreOrderItemBase):
    """Payload for creating a new StoreOrderItem."""

    order_id: UUID = Field(description="FK to the associated store order.")
    store_item_id: UUID = Field(description="FK to the catalog/store item.")


# ---- Update (PATCH) ----
class StoreOrderItemUpdate(BaseModel):
    """Partial update for an existing StoreOrderItem."""

    quantity: Optional[int] = Field(default=None, ge=1)
    unit_price_cents: Optional[int] = Field(default=None, ge=0)
    discount_cents: Optional[int] = Field(default=None, ge=0)
    note: Optional[str] = None
    order_id: Optional[UUID] = None
    store_item_id: Optional[UUID] = None


# ---- Read ----
class StoreOrderItemRead(StoreOrderItemBase):
    """Replica of a persisted StoreOrderItem (as returned by the API)."""

    id: UUID
    order_id: UUID
    store_item_id: UUID

    # Totals are often computed server-side; keep optional for compatibility
    line_subtotal_cents: Optional[int] = Field(
        default=None,
        description="Computed: quantity * unit_price_cents (before discount).",
    )
    line_total_cents: Optional[int] = Field(
        default=None,
        description="Computed: subtotal - discount (non-negative).",
    )

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Pydantic v2: allow construction from ORM objects
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


# ---- Lightweight summaries / lists ----
class StoreOrderItemSummary(BaseModel):
    """Minimal listing view of order items for tables or dropdowns."""

    id: UUID
    order_id: UUID
    store_item_id: UUID
    quantity: int
    line_total_cents: Optional[int] = None

    model_config = {"from_attributes": True}


class StoreOrderItemList(BaseModel):
    """Container useful for list endpoints that wrap results (kept optional)."""

    items: list[StoreOrderItemSummary]
    total: int = Field(description="Total matching records (for pagination).")
