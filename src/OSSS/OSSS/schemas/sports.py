"""
Pydantic schemas for Sport

Follows the same style/pattern as other schemas in `src/OSSS/schemas`.
Backed by model defined in `db/models/sports.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---- Base ----
class SportBase(BaseModel):
    """Shared fields between create/read/update for a Sport."""

    name: str = Field(..., max_length=128, description="Unique sport name (e.g., 'Basketball').")


# ---- Create ----
class SportCreate(SportBase):
    """Payload for creating a new Sport."""

    pass


# ---- Update (PATCH) ----
class SportUpdate(BaseModel):
    """Partial update for an existing Sport."""

    name: Optional[str] = Field(default=None, max_length=128)


# ---- Read ----
class SportRead(SportBase):
    """Replica of a persisted Sport (as returned by the API)."""

    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Pydantic v2: allow construction from ORM objects
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


# ---- Lightweight summaries / lists ----
class SportSummary(BaseModel):
    """Minimal listing view of sports for tables or dropdowns."""

    id: UUID
    name: str

    model_config = {"from_attributes": True}


class SportList(BaseModel):
    """Container useful for list endpoints that wrap results (kept optional)."""

    items: list[SportSummary]
    total: int = Field(description="Total matching records (for pagination).")
