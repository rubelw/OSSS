# src/OSSS/schemas/concession_item.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------- Base ----------
class ConcessionItemBase(BaseModel):
    """Fields shared by create/read/update for ConcessionItem."""
    model_config = ConfigDict(from_attributes=True)

    stand_id: UUID = Field(..., description="FK to concession_stands.id")
    name: Optional[str] = Field(None, max_length=255, description="Display name")
    price_cents: int = Field(..., ge=0, description="Item price in cents")
    inventory: Optional[int] = Field(None, ge=0, description="On-hand inventory (units)")
    active: bool = Field(True, description="Whether the item is active/for sale")


# ---------- Create ----------
class ConcessionItemCreate(ConcessionItemBase):
    """Payload to create a ConcessionItem."""
    # Inherits everything from base.


# ---------- Update (partial) ----------
class ConcessionItemUpdate(BaseModel):
    """Payload to partially update a ConcessionItem."""
    model_config = ConfigDict(from_attributes=True)

    stand_id: Optional[UUID] = Field(None, description="FK to concession_stands.id")
    name: Optional[str] = Field(None, max_length=255, description="Display name")
    price_cents: Optional[int] = Field(None, ge=0, description="Item price in cents")
    inventory: Optional[int] = Field(None, ge=0, description="On-hand inventory (units)")
    active: Optional[bool] = Field(None, description="Whether the item is active/for sale")


# ---------- Read ----------
class ConcessionItemRead(ConcessionItemBase):
    """Representation returned from the API for a ConcessionItem."""
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
