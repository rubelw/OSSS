"""
Pydantic schemas for StoreProduct

Follows the same style/pattern as other schemas in `src/OSSS/schemas`.
Backed by model defined in `db/models/store_products.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---- Base ----
class StoreProductBase(BaseModel):
    """Shared fields between create/read/update for a StoreProduct record."""

    name: str = Field(..., max_length=200, description="Display name of the product.")
    description: Optional[str] = Field(
        default=None, description="Optional longer description/HTML for the product."
    )
    sku: Optional[str] = Field(
        default=None, max_length=100, description="Optional SKU or merchant code."
    )
    price_cents: int = Field(
        ..., ge=0, description="Price in integer cents (avoid float rounding)."
    )
    image_url: Optional[str] = Field(
        default=None, description="Optional image URL for the catalog thumbnail."
    )
    is_active: bool = Field(
        default=True, description="Whether this product is visible/for sale."
    )
    inventory: Optional[int] = Field(
        default=None,
        ge=0,
        description="Optional available quantity; null means unlimited/not tracked.",
    )
    category: Optional[str] = Field(
        default=None, description="Optional logical category/bucket (e.g., 'Apparel')."
    )


# ---- Create ----
class StoreProductCreate(StoreProductBase):
    """Payload for creating a new StoreProduct."""

    school_id: UUID = Field(description="FK to the associated school.")


# ---- Update (PATCH) ----
class StoreProductUpdate(BaseModel):
    """Partial update for an existing StoreProduct."""

    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    sku: Optional[str] = Field(default=None, max_length=100)
    price_cents: Optional[int] = Field(default=None, ge=0)
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    inventory: Optional[int] = Field(default=None, ge=0)
    category: Optional[str] = None
    school_id: Optional[UUID] = None


# ---- Read ----
class StoreProductRead(StoreProductBase):
    """Replica of a persisted StoreProduct (as returned by the API)."""

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
class StoreProductSummary(BaseModel):
    """Minimal listing view of store products for tables or dropdowns."""

    id: UUID
    school_id: UUID
    name: str
    price_cents: int
    is_active: bool

    model_config = {"from_attributes": True}


class StoreProductList(BaseModel):
    """Container useful for list endpoints that wrap results (kept optional)."""

    items: list[StoreProductSummary]
    total: int = Field(description="Total matching records (for pagination).")
