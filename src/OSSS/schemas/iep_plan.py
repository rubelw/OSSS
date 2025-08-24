from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class IepPlanOut(ORMBase):
    id: str
    special_ed_case_id: str
    effective_start: date
    effective_end: Optional[date] = None
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
