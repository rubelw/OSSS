from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

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
