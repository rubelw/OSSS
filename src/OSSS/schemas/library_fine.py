from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class LibraryFineOut(ORMBase):
    id: str
    person_id: str
    amount: Decimal
    reason: Optional[str] = None
    assessed_on: date
    paid_on: Optional[date] = None
    created_at: datetime
    updated_at: datetime
