# src/OSSS/schemas/games.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# -------------------------
# Base / shared attributes
# -------------------------
class GameBase(BaseModel):
    """
    Shared attributes for Game.
    Adjust names/types to match OSSS.db.models.games.Game exactly.
    """
    # REQUIRED relationships (very likely present)
    home_team_id: UUID = Field(..., description="Home team ID")
    away_team_id: UUID = Field(..., description="Away team ID")

    # Scheduling & context
    starts_at: datetime = Field(..., description="Scheduled start datetime (UTC)")
    venue_id: Optional[UUID] = Field(None, description="Venue / facility ID")
    season_id: Optional[UUID] = Field(None, description="Season ID")
    organization_id: Optional[UUID] = Field(None, description="Owning organization ID")

    # Status & results
    status: Optional[str] = Field(
        None,
        description="Game status (e.g., scheduled, in_progress, final, canceled, postponed)",
    )
    home_score: Optional[int] = Field(None, ge=0, description="Final/known home score")
    away_score: Optional[int] = Field(None, ge=0, description="Final/known away score")

    # Misc
    notes: Optional[str] = Field(None, description="Freeform notes")


# -------------------------
# Create / Update payloads
# -------------------------
class GameCreate(GameBase):
    """
    Payload for creating a Game.
    Keep only fields you actually allow on POST.
    """
    model_config = ConfigDict(from_attributes=True)


class GameUpdate(BaseModel):
    """
    Partial update (PATCH) for Game.
    All fields optional.
    """
    model_config = ConfigDict(from_attributes=True)

    home_team_id: Optional[UUID] = None
    away_team_id: Optional[UUID] = None
    starts_at: Optional[datetime] = None
    venue_id: Optional[UUID] = None
    season_id: Optional[UUID] = None
    organization_id: Optional[UUID] = None
    status: Optional[str] = None
    home_score: Optional[int] = Field(None, ge=0)
    away_score: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


# -------------------------
# Read models (responses)
# -------------------------
class GameOut(GameBase):
    """
    Read model returned by the API.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Game ID")
    created_at: Optional[datetime] = Field(None, description="Created timestamp")
    updated_at: Optional[datetime] = Field(None, description="Updated timestamp")


# -------------------------
# Filters / query params
# -------------------------
class GameFilters(BaseModel):
    """
    Query-string filters for listing Games.
    Keep aligned with your list endpoint.
    """
    model_config = ConfigDict(from_attributes=True)

    # Common filters
    team_id: Optional[UUID] = Field(
        None, description="Return games where this team is home OR away"
    )
    home_team_id: Optional[UUID] = None
    away_team_id: Optional[UUID] = None
    season_id: Optional[UUID] = None
    organization_id: Optional[UUID] = None
    venue_id: Optional[UUID] = None
    status: Optional[str] = None

    # Time range
    starts_at_from: Optional[datetime] = Field(
        None, description="Return games with starts_at >= this time"
    )
    starts_at_to: Optional[datetime] = Field(
        None, description="Return games with starts_at <= this time"
    )

    # Free-text search if you support it
    q: Optional[str] = Field(
        None, description="Optional free-text search (notes, venue name, etc.)"
    )


# -------------------------
# Lightweight variants (optional)
# -------------------------
class GameRef(BaseModel):
    """
    Super-lightweight reference to a Game, for embedding.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    starts_at: datetime
    status: Optional[str] = None
