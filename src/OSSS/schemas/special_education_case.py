from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class SpecialEducationCaseOut(ORMBase):
    id: str
    student_id: str
    eligibility: Optional[str] = None
    case_opened: Optional[date] = None
    case_closed: Optional[date] = None
    created_at: datetime
    updated_at: datetime
