"""
Pydantic schemas for Team

Follows the same style/pattern as other schemas in `src/OSSS/schemas`.
Backed by model defined in `db/models/teams.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

# Keep enum aligned with the SQLAlchemy model
try:
    from OSSS.db.models.common_enums import Level  # type: ignore
except Exception:  # lightweight fallback for typing/runtime in isolation
    from enum import Enum

    class Level(str, Enum):  # type: ignore[no-redef]
        varsity = "varsity"
        junior_varsity = "junior_varsity"
        freshman = "freshman"
        middle_school = "middle_school"
        club = "club"


# ---- Base ----
class TeamBase(BaseModel):
    """Shared fields between create/read/update for a Team record."""

    name: str = Field(..., max_length=128, description="Team display name.")
    level: Level = Field(..., description="Competition level (enum).")
    mascot: Optional[str] = Field(default=None, max_length=128)
    primary_color: Optional[str] = Field(
        default=None, description="Hex or CSS color token (primary)."
    )
    secondary_color: Optional[str] = Field(
        default=None, description="Hex or CSS color token (secondary)."
    )
    is_active: bool = Field(default=True, description="Whether this team is active.")


# ---- Create ----
class TeamCreate(TeamBase):
    """Payload for creating a new Team."""

    school_id: UUID = Field(description="FK to the associated school.")
    sport_id: UUID = Field(description="FK to the associated sport.")


# ---- Update (PATCH) ----
class TeamUpdate(BaseModel):
    """Partial update for an existing Team."""

    name: Optional[str] = Field(default=None, max_length=128)
    level: Optional[Level] = None
    mascot: Optional[str] = Field(default=None, max_length=128)
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    is_active: Optional[bool] = None
    school_id: Optional[UUID] = None
    sport_id: Optional[UUID] = None


# ---- Read ----
class TeamRead(TeamBase):
    """Replica of a persisted Team (as returned by the API)."""

    id: UUID
    school_id: UUID
    sport_id: UUID

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Pydantic v2: allow construction from ORM objects
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


# ---- Lightweight summaries / lists ----
class TeamSummary(BaseModel):
    """Minimal listing view of teams for tables or dropdowns."""

    id: UUID
    school_id: UUID
    sport_id: UUID
    name: str
    level: Level
    is_active: bool

    model_config = {"from_attributes": True}


class TeamList(BaseModel):
    """Container useful for list endpoints that wrap results (kept optional)."""

    items: list[TeamSummary]
    total: int = Field(description="Total matching records (for pagination).")
