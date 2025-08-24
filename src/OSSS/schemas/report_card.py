from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class ReportCardOut(ORMBase):
    id: str
    student_id: str
    term_id: str
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
