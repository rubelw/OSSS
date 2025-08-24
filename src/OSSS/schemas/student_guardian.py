from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class StudentGuardianOut(ORMBase):
    student_id: str
    guardian_id: str
    custody: Optional[str] = None
    is_primary: bool
    contact_order: Optional[int] = None
    created_at: datetime
    updated_at: datetime
