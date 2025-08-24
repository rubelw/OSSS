from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class WaiverOut(ORMBase):
    id: str
    student_id: str
    reason: Optional[str] = None
    amount: Optional[Decimal] = None
    granted_on: Optional[date] = None
    created_at: datetime
    updated_at: datetime
