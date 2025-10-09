# src/OSSS/schemas/concession_sale_items.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class ConcessionSaleItemBase(BaseModel):
    """
    Shared fields for ConcessionSaleItem.
    """
    sale_id: str = Field(..., description="FK to concession_sales.id")
    item_id: str = Field(..., description="FK to concession_items.id")
    quantity: int = Field(..., gt=0, description="How many units were sold")
    price_cents: int = Field(..., ge=0, description="Unit price in cents")


class ConcessionSaleItemCreate(ConcessionSaleItemBase):
    """
    Payload to create a ConcessionSaleItem.
    """
    pass


class ConcessionSaleItemUpdate(BaseModel):
    """
    Partial update for a ConcessionSaleItem.
    All fields optional.
    """
    sale_id: Optional[str] = Field(None, description="FK to concession_sales.id")
    item_id: Optional[str] = Field(None, description="FK to concession_items.id")
    quantity: Optional[int] = Field(None, gt=0, description="How many units were sold")
    price_cents: Optional[int] = Field(None, ge=0, description="Unit price in cents")


class ConcessionSaleItem(ConcessionSaleItemBase):
    """
    Read model for a ConcessionSaleItem.
    """
    id: str

    # Pydantic v2: enable ORM mode
    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "ConcessionSaleItemBase",
    "ConcessionSaleItemCreate",
    "ConcessionSaleItemUpdate",
    "ConcessionSaleItem",
]
