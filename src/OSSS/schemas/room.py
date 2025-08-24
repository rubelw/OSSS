from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class RoomOut(ORMBase):
    id: str
    school_id: str
    name: str
    capacity: Optional[int] = None
    created_at: datetime
    updated_at: datetime
