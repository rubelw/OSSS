from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class AcademicTermOut(ORMBase):
    id: str
    school_id: str
    name: str
    type: Optional[str] = None
    start_date: date
    end_date: date
    created_at: datetime
    updated_at: datetime
