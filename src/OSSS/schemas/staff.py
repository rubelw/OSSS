from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class StaffOut(ORMBase):
    id: str
    employee_number: Optional[str] = None
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
