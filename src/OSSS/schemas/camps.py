# src/OSSS/schemas/camps.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


# -----------------------------
# Shared fields (from the model)
# -----------------------------
class CampBase(BaseModel):
    """Fields shared by create/update/read for Camp."""

    # NOTE: your model maps GUID() columns to Python str (Mapped[str]),
    # so we keep these typed as str to match the DB layer.
    school_id: str = Field(..., description="FK to schools.id")

    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None

    start_date: Optional[date] = None
    end_date: Optional[date] = None

    price_cents: Optional[int] = Field(
        None, ge=0, description="Price in cents (optional)"
    )
    capacity: Optional[int] = Field(
        None, ge=0, description="Max capacity (optional)"
    )

    location: Optional[str] = Field(None, max_length=255)

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


# -------------
# Write schemas
# -------------
class CampCreate(CampBase):
    """Payload for creating a Camp."""
    # If create-time required fields differ from CampBase,
    # tighten them here. Right now, school_id is required; others optional.
    pass


class CampUpdate(BaseModel):
    """Payload for partially updating a Camp."""
    school_id: Optional[str] = None

    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None

    start_date: Optional[date] = None
    end_date: Optional[date] = None

    price_cents: Optional[int] = Field(None, ge=0)
    capacity: Optional[int] = Field(None, ge=0)

    location: Optional[str] = Field(None, max_length=255)

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


# ------------
# Read schema
# ------------
class CampRead(CampBase):
    """Representation returned from the API for a Camp."""
    id: str
    created_at: datetime
    updated_at: datetime

    # Enable ORM -> Pydantic conversion
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


__all__ = [
    "CampBase",
    "CampCreate",
    "CampUpdate",
    "CampRead",
]
