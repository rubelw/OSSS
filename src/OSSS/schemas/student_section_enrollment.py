from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class StudentSectionEnrollmentCreate(BaseModel):
    student_id: str
    section_id: str
    added_on: date
    dropped_on: Optional[date] = None
    seat_time_minutes: Optional[int] = None


class StudentSectionEnrollmentOut(ORMBase):
    id: str
    student_id: str
    section_id: str
    added_on: date
    dropped_on: Optional[date] = None
    seat_time_minutes: Optional[int] = None
    created_at: datetime
    updated_at: datetime
