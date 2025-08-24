from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

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
