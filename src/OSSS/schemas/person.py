from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class PersonOut(ORMBase):
    id: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    dob: Optional[date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    created_at: datetime
    updated_at: datetime
