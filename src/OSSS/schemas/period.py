from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class PeriodOut(ORMBase):
    id: str
    bell_schedule_id: str
    name: str
    start_time: time
    end_time: time
    sequence: Optional[int] = None
    created_at: datetime
    updated_at: datetime
