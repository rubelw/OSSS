from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class StudentSectionEnrollmentOut(ORMBase):
    id: str
    student_id: str
    section_id: str
    added_on: date
    dropped_on: Optional[date] = None
    seat_time_minutes: Optional[int] = None
    created_at: datetime
    updated_at: datetime
