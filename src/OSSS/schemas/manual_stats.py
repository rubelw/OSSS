
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class ManualStatBase(BaseModel):
    game_id: str
    team_id: str
    athlete_id: Optional[str] = None
    payload: dict
    class Config:
        from_attributes = True

class ManualStatCreate(ManualStatBase):
    id: Optional[str] = None

class ManualStatRead(ManualStatBase):
    id: str
    created_at: datetime
