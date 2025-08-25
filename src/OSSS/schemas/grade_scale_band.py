from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class GradeScaleBandCreate(BaseModel):
    grade_scale_id: str
    label: str
    min_value: Decimal
    max_value: Decimal
    gpa_points: Optional[Decimal] = None


class GradeScaleBandOut(ORMBase):
    id: str
    grade_scale_id: str
    label: str
    min_value: Decimal
    max_value: Decimal
    gpa_points: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
