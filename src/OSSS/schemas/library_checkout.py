from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class LibraryCheckoutOut(ORMBase):
    id: str
    item_id: str
    person_id: str
    checked_out_on: date
    due_on: date
    returned_on: Optional[date] = None
    created_at: datetime
    updated_at: datetime
