from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class LibraryHoldOut(ORMBase):
    id: str
    item_id: str
    person_id: str
    placed_on: date
    expires_on: Optional[date] = None
    created_at: datetime
    updated_at: datetime
