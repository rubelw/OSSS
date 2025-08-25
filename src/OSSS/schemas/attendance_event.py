# schemas/attendanceevent.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field

from .base import ORMBase


class AttendanceEventCreate(BaseModel):
    student_id: str
    section_meeting_id: Optional[str] = None
    date: date
    code: str = Field(..., min_length=1)
    minutes: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None


class AttendanceEventOut(ORMBase):
    id: str
    student_id: str
    section_meeting_id: Optional[str] = None
    date: date
    code: str
    minutes: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
