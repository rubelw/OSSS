
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from .common import Level, LiveStatus

class GameBase(BaseModel):
    season_id: Optional[str] = None
    home_team_id: Optional[str] = None
    away_team_id: Optional[str] = None
    level: Level
    status: LiveStatus = "scheduled"
    start_at: Optional[datetime] = None
    location: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    class Config:
        from_attributes = True

class GameCreate(GameBase):
    id: Optional[str] = None

class GameRead(GameBase):
    id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
