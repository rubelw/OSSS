from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class SectionMeetingOut(ORMBase):
    id: str
    section_id: str
    day_of_week: int
    period_id: Optional[str] = None
    room_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
