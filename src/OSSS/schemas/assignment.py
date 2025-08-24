from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class AssignmentOut(ORMBase):
    id: str
    section_id: str
    category_id: Optional[str] = None
    name: str
    due_date: Optional[date] = None
    points_possible: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
