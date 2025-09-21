
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class ScoreEntryBase(BaseModel):
    game_id: str
    submitted_by: Optional[str] = None
    submitted_at: Optional[datetime] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    class Config:
        from_attributes = True

class ScoreEntryCreate(ScoreEntryBase):
    id: Optional[str] = None

class ScoreEntryRead(ScoreEntryBase):
    id: str
