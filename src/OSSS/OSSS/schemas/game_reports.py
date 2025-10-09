# src/OSSS/schemas/game_reports.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Core / Base
# ---------------------------------------------------------------------------
class GameReportBase(BaseModel):
    """Fields shared across create/update/read."""
    game_id: UUID
    report: Optional[Dict[str, Any]] = None
    # generated_at is produced server-side in the model (default=utcnow),
    # but we accept it here so callers can override if needed.
    generated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
class GameReportCreate(GameReportBase):
    """Payload for creating a game report."""
    # game_id is required via GameReportBase
    pass


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
class GameReportUpdate(BaseModel):
    """Payload for partial updates to a game report."""
    game_id: Optional[UUID] = None
    report: Optional[Dict[str, Any]] = None
    generated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Out / Read
# ---------------------------------------------------------------------------
class GameReportOut(GameReportBase):
    """Response model for reading game reports."""
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Enable ORM mode (Pydantic v2)
    model_config = ConfigDict(from_attributes=True)
