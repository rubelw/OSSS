from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class FinalGradeOut(ORMBase):
    id: str
    student_id: str
    section_id: str
    grading_period_id: str
    numeric_grade: Optional[Decimal] = None
    letter_grade: Optional[str] = None
    credits_earned: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
