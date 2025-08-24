from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class NurseVisitOut(ORMBase):
    id: str
    student_id: str
    visited_at: datetime
    reason: Optional[str] = None
    disposition: Optional[str] = None
    created_at: datetime
    updated_at: datetime
