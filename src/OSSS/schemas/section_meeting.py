from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class SectionMeetingCreate(BaseModel):
    section_id: str
    day_of_week: int
    period_id: Optional[str] = None
    room_id: Optional[str] = None


class SectionMeetingOut(ORMBase):
    id: str
    section_id: str
    day_of_week: int
    period_id: Optional[str] = None
    room_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
