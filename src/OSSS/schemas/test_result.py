from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class TestResultOut(ORMBase):
    id: str
    administration_id: str
    student_id: str
    scale_score: Optional[Decimal] = None
    percentile: Optional[Decimal] = None
    performance_level: Optional[str] = None
    created_at: datetime
    updated_at: datetime
