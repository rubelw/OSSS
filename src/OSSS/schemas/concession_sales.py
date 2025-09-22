# src/OSSS/schemas/concession_sales.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ---------- Base ----------

class ConcessionSaleBase(BaseModel):
    """Shared fields for ConcessionSale."""
    stand_id: UUID = Field(..., description="FK to concession_stands.id")
    event_id: Optional[UUID] = Field(None, description="FK to events.id (nullable)")
    total_cents: int = Field(
        ...,
        ge=0,
        description="Total sale amount in cents (non-negative).",
    )
    sold_at: Optional[datetime] = Field(
        None,
        description="Timestamp when the sale occurred; defaults in DB if not provided.",
    )

    model_config = ConfigDict(from_attributes=True)


# ---------- Create ----------

class ConcessionSaleCreate(ConcessionSaleBase):
    """
    Payload for creating a ConcessionSale.

    Notes:
    - sold_at may be omitted to use the DB default (e.g., CURRENT_TIMESTAMP).
    - event_id may be null for stand-only sales.
    """
    pass


# ---------- Update (partial) ----------

class ConcessionSaleUpdate(BaseModel):
    """Partial update for ConcessionSale; all fields optional."""
    stand_id: Optional[UUID] = Field(None, description="FK to concession_stands.id")
    event_id: Optional[UUID] = Field(None, description="FK to events.id (nullable)")
    total_cents: Optional[int] = Field(
        None,
        ge=0,
        description="Total sale amount in cents (non-negative).",
    )
    sold_at: Optional[datetime] = Field(None, description="When the sale occurred")

    model_config = ConfigDict(from_attributes=True)


# ---------- Read/Out ----------

class ConcessionSaleRead(ConcessionSaleBase):
    """Representation returned from the API/DB."""
    id: UUID = Field(..., description="Primary key")

    # If you later want to include related objects, add light-weight refs here, e.g.:
    # stand: Optional[ConcessionStandRef] = None
    # event: Optional[EventRef] = None


__all__ = [
    "ConcessionSaleBase",
    "ConcessionSaleCreate",
    "ConcessionSaleUpdate",
    "ConcessionSaleRead",
]
