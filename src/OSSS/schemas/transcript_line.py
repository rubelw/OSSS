from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class TranscriptLineOut(ORMBase):
    id: str
    student_id: str
    course_id: Optional[str] = None
    term_id: Optional[str] = None
    credits_attempted: Optional[Decimal] = None
    credits_earned: Optional[Decimal] = None
    final_letter: Optional[str] = None
    final_numeric: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
