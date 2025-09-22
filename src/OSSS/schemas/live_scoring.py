"""
Pydantic schemas for LiveScoring

Follows the same style/pattern as other schemas in `src/OSSS/schemas`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from OSSS.db.models.common_enums import LiveStatus


# ---- Base ----
class LiveScoringBase(BaseModel):
    """Shared fields between create/read/update for a LiveScoring session."""

    status: LiveStatus = Field(
        default=LiveStatus.live,
        description="Current live scoring status.",
    )
    feed_url: Optional[str] = Field(
        default=None,
        description="Optional URL to an external/live-scoring feed (vendor-specific).",
    )
    started_at: Optional[datetime] = Field(
        default=None, description="When the live scoring session started."
    )
    ended_at: Optional[datetime] = Field(
        default=None, description="When the live scoring session ended (if ended)."
    )
    last_event_at: Optional[datetime] = Field(
        default=None, description="Timestamp of the most recent ingested scoring event."
    )


# ---- Create ----
class LiveScoringCreate(LiveScoringBase):
    """Payload for creating a new LiveScoring session."""

    # Relationship foreign key
    game_id: UUID = Field(description="FK to the associated game.")


# ---- Update (PATCH) ----
class LiveScoringUpdate(BaseModel):
    """Partial update for an existing LiveScoring session."""

    status: Optional[LiveStatus] = None
    feed_url: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    last_event_at: Optional[datetime] = None


# ---- Read ----
class LiveScoringRead(LiveScoringBase):
    """Replica of a persisted LiveScoring session (as returned by the API)."""

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
class LiveScoringSummary(BaseModel):
    """Minimal listing view of live scoring sessions for tables or dropdowns."""

    id: UUID
    game_id: UUID
    status: LiveStatus
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LiveScoringList(BaseModel):
    """Container useful for list endpoints that wrap results (kept optional)."""

    items: list[LiveScoringSummary]
    total: int = Field(description="Total matching records (for pagination).")
