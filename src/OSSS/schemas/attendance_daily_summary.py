# schemas/attendancedailysummary.py
from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel, Field

from .base import ORMBase


class AttendanceDailySummaryCreate(BaseModel):
    student_id: str
    date: date
    present_minutes: int = Field(default=0, ge=0)
    absent_minutes: int = Field(default=0, ge=0)
    tardy_minutes: int = Field(default=0, ge=0)


class AttendanceDailySummaryOut(ORMBase):
    id: str
    student_id: str
    date: date
    present_minutes: int
    absent_minutes: int
    tardy_minutes: int
    created_at: datetime
    updated_at: datetime
