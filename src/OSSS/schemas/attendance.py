# schemas/attendance.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .base import ORMBase


class AttendanceCreate(BaseModel):
    meeting_id: str
    user_id: str
    status: Optional[str] = Field(default=None, max_length=16)
    arrived_at: Optional[datetime] = None
    left_at: Optional[datetime] = None


class AttendanceOut(ORMBase):
    meeting_id: str
    user_id: str
    status: Optional[str] = None
    arrived_at: Optional[datetime] = None
    left_at: Optional[datetime] = None
