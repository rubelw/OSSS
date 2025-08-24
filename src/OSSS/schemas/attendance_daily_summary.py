from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class AttendanceDailySummaryOut(ORMBase):
    id: str
    student_id: str
    date: date
    present_minutes: int
    absent_minutes: int
    tardy_minutes: int
    created_at: datetime
    updated_at: datetime
