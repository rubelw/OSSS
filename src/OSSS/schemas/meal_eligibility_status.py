from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict
from pydantic import BaseModel

from .base import ORMBase


class MealEligibilityStatusCreate(BaseModel):
    student_id: str
    status: str  # e.g., "free" | "reduced" | "paid"
    effective_start: date
    effective_end: Optional[date] = None


class MealEligibilityStatusOut(ORMBase):
    id: str
    student_id: str
    status: str
    effective_start: date
    effective_end: Optional[date] = None
    created_at: datetime
    updated_at: datetime
