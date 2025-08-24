from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class GradeScaleBandOut(ORMBase):
    id: str
    grade_scale_id: str
    label: str
    min_value: Decimal
    max_value: Decimal
    gpa_points: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
