from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class CourseOut(ORMBase):
    id: str
    school_id: str
    subject_id: Optional[str] = None
    name: str
    code: Optional[str] = None
    credit_hours: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
