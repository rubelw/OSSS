from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class PersonAddressOut(ORMBase):
    person_id: str
    address_id: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime
