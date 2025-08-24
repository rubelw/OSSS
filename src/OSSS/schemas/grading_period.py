from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class GradingPeriodOut(ORMBase):
    id: str
    term_id: str
    name: str
    start_date: date
    end_date: date
    created_at: datetime
    updated_at: datetime
