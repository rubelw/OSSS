# OSSS/schemas/attendance.py
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import Field
from OSSS.schemas.base import APIModel

class AttendanceBase(APIModel):
    meeting_id: str = Field(...)
    user_id: str = Field(...)
    status: Optional[str] = Field(None, max_length=16)
    arrived_at: Optional[datetime] = None
    left_at: Optional[datetime] = None

class AttendanceCreate(AttendanceBase): pass
class AttendanceReplace(AttendanceBase): pass

class AttendancePatch(APIModel):
    meeting_id: Optional[str] = None
    user_id: Optional[str] = None
    status: Optional[str] = None
    arrived_at: Optional[datetime] = None
    left_at: Optional[datetime] = None

class AttendanceOut(AttendanceBase):
    id: str

class AttendanceList(APIModel):
    items: List[AttendanceOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
