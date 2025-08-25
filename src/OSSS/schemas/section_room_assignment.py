from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class SectionRoomAssignmentCreate(BaseModel):
    section_id: str
    room_id: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class SectionRoomAssignmentOut(ORMBase):
    id: str
    section_id: str
    room_id: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime
