
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from .common import EventType

class EventCreate(BaseModel):
    school_id: str
    team_id: Optional[str] = None
    type: EventType = "Other"
    title: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    class Config:
        from_attributes = True

class EventRead(EventCreate):
    id: str
