from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class StudentOut(ORMBase):
    id: str
    student_number: Optional[str] = None
    graduation_year: Optional[int] = None
    created_at: datetime
    updated_at: datetime
