from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class DistrictOut(ORMBase):
    id: str
    name: str
    code: Optional[str] = None
    created_at: datetime
    updated_at: datetime
