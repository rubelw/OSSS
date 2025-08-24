from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class StudentTransportationAssignmentOut(ORMBase):
    id: str
    student_id: str
    route_id: Optional[str] = None
    stop_id: Optional[str] = None
    direction: Optional[str] = None
    effective_start: date
    effective_end: Optional[date] = None
    created_at: datetime
    updated_at: datetime
