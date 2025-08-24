from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class StudentProgramEnrollmentOut(ORMBase):
    id: str
    student_id: str
    program_name: str
    start_date: date
    end_date: Optional[date] = None
    status: Optional[str] = None
    created_at: datetime
    updated_at: datetime
