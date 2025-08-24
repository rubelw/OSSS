from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class EmergencyContactOut(ORMBase):
    id: str
    person_id: str
    contact_name: str
    relationship: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime
