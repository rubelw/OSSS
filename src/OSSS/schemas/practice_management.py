
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class PracticeCreate(BaseModel):
    team_id: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    class Config:
        from_attributes = True

class PracticeRead(PracticeCreate):
    id: str
