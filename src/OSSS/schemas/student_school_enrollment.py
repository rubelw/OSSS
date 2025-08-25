from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class StudentSchoolEnrollmentCreate(BaseModel):
    student_id: str
    school_id: str
    entry_date: date
    exit_date: Optional[date] = None
    status: str
    exit_reason: Optional[str] = None


class StudentSchoolEnrollmentOut(ORMBase):
    id: str
    student_id: str
    school_id: str
    entry_date: date
    exit_date: Optional[date] = None
    status: str
    exit_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
