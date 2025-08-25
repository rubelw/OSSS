from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class StudentProgramEnrollmentCreate(BaseModel):
    student_id: str
    program_name: str
    start_date: date
    end_date: Optional[date] = None
    status: Optional[str] = None


class StudentProgramEnrollmentOut(ORMBase):
    id: str
    student_id: str
    program_name: str
    start_date: date
    end_date: Optional[date] = None
    status: Optional[str] = None
    created_at: datetime
    updated_at: datetime
