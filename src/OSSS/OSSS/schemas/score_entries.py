"""
Pydantic schemas for ScoreEntry

Follows the same style/pattern as other schemas in `src/OSSS/schemas`.
Backed by model defined in `db/models/score_entry.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---- Base ----
class ScoreEntryBase(BaseModel):
    """Shared fields between create/read/update for a ScoreEntry record."""

    submitted_by: Optional[str] = Field(
        default=None,
        description="User identifier who submitted the score entry (optional).",
    )
    submitted_at: Optional[datetime] = Field(
        default=None,
        description="When the score entry was submitted (UTC). If omitted on create, backend defaults.",
    )
    source: Optional[str] = Field(
        default=None,
        description="Origin of the entry, e.g. 'manual', 'import', or 'live' (optional).",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Free-text notes for the score entry (optional).",
    )


# ---- Create ----
class ScoreEntryCreate(ScoreEntryBase):
    """Payload for creating a new ScoreEntry."""

    game_id: UUID = Field(description="FK to the associated game.")


# ---- Update (PATCH) ----
class ScoreEntryUpdate(BaseModel):
    """Partial update for an existing ScoreEntry."""

    submitted_by: Optional[str] = None
    submitted_at: Optional[datetime] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    game_id: Optional[UUID] = None


# ---- Read ----
class ScoreEntryRead(ScoreEntryBase):
    """Replica of a persisted ScoreEntry (as returned by the API)."""

    id: UUID
    game_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Pydantic v2: allow construction from ORM objects
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


# ---- Lightweight summaries / lists ----
class ScoreEntrySummary(BaseModel):
    """Minimal listing view of score entries for tables or dropdowns."""

    id: UUID
    game_id: UUID
    submitted_by: Optional[str] = None
    submitted_at: Optional[datetime] = None
    source: Optional[str] = None

    model_config = {"from_attributes": True}


class ScoreEntryList(BaseModel):
    """Container useful for list endpoints that wrap results (kept optional)."""

    items: list[ScoreEntrySummary]
    total: int = Field(description="Total matching records (for pagination).")
