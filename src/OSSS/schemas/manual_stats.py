"""
Pydantic schemas for ManualStat

Follows the same style/pattern as other schemas in `src/OSSS/schemas`.
Backed by model defined in `db/models/manual_stats.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---- Base ----
class ManualStatBase(BaseModel):
    """Shared fields between create/read/update for a ManualStat record."""

    payload: dict = Field(
        default_factory=dict,
        description="Arbitrary per-sport stats payload (JSON).",
    )
    athlete_id: Optional[str] = Field(
        default=None,
        description="Optional athlete identifier (string, may not be a FK).",
    )


# ---- Create ----
class ManualStatCreate(ManualStatBase):
    """Payload for creating a new ManualStat."""

    game_id: UUID = Field(description="FK to the associated game.")
    team_id: UUID = Field(description="FK to the associated team.")


# ---- Update (PATCH) ----
class ManualStatUpdate(BaseModel):
    """Partial update for an existing ManualStat."""

    payload: Optional[dict] = None
    athlete_id: Optional[str] = None


# ---- Read ----
class ManualStatRead(ManualStatBase):
    """Replica of a persisted ManualStat (as returned by the API)."""

    id: UUID
    game_id: UUID
    team_id: UUID
    created_at: datetime

    # Pydantic v2: allow construction from ORM objects
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


# ---- Lightweight summaries / lists ----
class ManualStatSummary(BaseModel):
    """Minimal listing view of manual stats for tables or dropdowns."""

    id: UUID
    game_id: UUID
    team_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class ManualStatList(BaseModel):
    """Container useful for list endpoints that wrap results (kept optional)."""

    items: list[ManualStatSummary]
    total: int = Field(description="Total matching records (for pagination).")
