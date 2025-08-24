from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class BellScheduleOut(ORMBase):
    id: str
    school_id: str
    name: str
    created_at: datetime
    updated_at: datetime
