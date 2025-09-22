"""
Pydantic schemas for Trip

Follows the same style/pattern as other schemas in `src/OSSS/schemas`.
Backed by model defined in `db/models/trip.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ---- Base ----
class TripBase(BaseModel):
    """Shared fields between create/read/update for a Trip record."""

    provider: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Transportation provider, e.g., 'district', 'charter', or 'parent'.",
    )
    bus_number: Optional[str] = Field(default=None, max_length=64)
    driver_name: Optional[str] = Field(default=None, max_length=128)
    depart_at: Optional[datetime] = Field(
        default=None,
        description="Planned departure (timezone-aware UTC).",
    )
    return_at: Optional[datetime] = Field(
        default=None,
        description="Planned return (timezone-aware UTC).",
    )
    notes: Optional[str] = Field(default=None, description="Optional free-text notes.")
    status: Optional[str] = Field(
        default=None,
        max_length=32,
        description="Trip state, e.g., 'requested', 'booked', 'completed', 'canceled'.",
    )

    @model_validator(mode="after")
    def _validate_time_range(self):  # type: ignore[override]
        if self.depart_at and self.return_at and self.return_at < self.depart_at:
            raise ValueError("return_at must be >= depart_at")
        return self


# ---- Create ----
class TripCreate(TripBase):
    """Payload for creating a new Trip."""

    event_id: UUID = Field(description="FK to the associated event.")


# ---- Update (PATCH) ----
class TripUpdate(BaseModel):
    """Partial update for an existing Trip."""

    provider: Optional[str] = Field(default=None, max_length=64)
    bus_number: Optional[str] = Field(default=None, max_length=64)
    driver_name: Optional[str] = Field(default=None, max_length=128)
    depart_at: Optional[datetime] = None
    return_at: Optional[datetime] = None
    notes: Optional[str] = None
    status: Optional[str] = Field(default=None, max_length=32)
    event_id: Optional[UUID] = None

    @model_validator(mode="after")
    def _validate_time_range(self):  # type: ignore[override]
        if self.depart_at and self.return_at and self.return_at < self.depart_at:
            raise ValueError("return_at must be >= depart_at")
        return self


# ---- Read ----
class TripRead(TripBase):
    """Replica of a persisted Trip (as returned by the API)."""

    id: UUID
    event_id: UUID

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Pydantic v2: allow construction from ORM objects
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


# ---- Lightweight summaries / lists ----
class TripSummary(BaseModel):
    """Minimal listing view of trips for tables or dropdowns."""

    id: UUID
    event_id: UUID
    provider: Optional[str] = None
    depart_at: Optional[datetime] = None
    return_at: Optional[datetime] = None
    status: Optional[str] = None

    model_config = {"from_attributes": True}


class TripList(BaseModel):
    """Container useful for list endpoints that wrap results (kept optional)."""

    items: list[TripSummary]
    total: int = Field(description="Total matching records (for pagination).")
