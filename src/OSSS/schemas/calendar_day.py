from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from pydantic import BaseModel
from .base import ORMBase


class CalendarDayCreate(BaseModel):
    calendar_id: str
    date: date
    day_type: str
    notes: Optional[str] = None


class CalendarDayOut(ORMBase):
    id: str
    calendar_id: str
    date: date
    day_type: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
