from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class PersonContactOut(ORMBase):
    person_id: str
    contact_id: str
    label: Optional[str] = None
    is_primary: bool
    is_emergency: bool
    created_at: datetime
    updated_at: datetime
