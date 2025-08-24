from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class AttendanceCodeOut(ORMBase):
    code: str
    description: Optional[str] = None
    is_present: bool
    is_excused: bool
    created_at: datetime
    updated_at: datetime
