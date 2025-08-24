from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class AssignmentCategoryOut(ORMBase):
    id: str
    section_id: str
    name: str
    weight: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
