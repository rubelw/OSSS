from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class AccommodationOut(ORMBase):
    id: str
    iep_plan_id: Optional[str] = None
    applies_to: Optional[str] = None
    description: str
    created_at: datetime
    updated_at: datetime
