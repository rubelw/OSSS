from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class EllPlanCreate(BaseModel):
    student_id: str
    level: Optional[str] = None
    effective_start: date
    effective_end: Optional[date] = None


class EllPlanOut(ORMBase):
    id: str
    student_id: str
    level: Optional[str] = None
    effective_start: date
    effective_end: Optional[date] = None
    created_at: datetime
    updated_at: datetime
