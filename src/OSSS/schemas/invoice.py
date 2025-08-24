from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class InvoiceOut(ORMBase):
    id: str
    student_id: str
    issued_on: date
    due_on: Optional[date] = None
    status: str
    created_at: datetime
    updated_at: datetime
