from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class GradebookEntryOut(ORMBase):
    id: str
    assignment_id: str
    student_id: str
    score: Optional[Decimal] = None
    submitted_at: Optional[datetime] = None
    late: bool
    created_at: datetime
    updated_at: datetime
