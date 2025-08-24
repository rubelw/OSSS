from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class ConsentOut(ORMBase):
    id: str
    person_id: str
    consent_type: str
    granted: bool
    effective_date: date
    expires_on: Optional[date] = None
    created_at: datetime
    updated_at: datetime
