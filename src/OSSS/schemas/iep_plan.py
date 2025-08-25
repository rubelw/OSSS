from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class IepPlanCreate(BaseModel):
    special_ed_case_id: str
    effective_start: date
    effective_end: Optional[date] = None
    summary: Optional[str] = None


class IepPlanOut(ORMBase):
    id: str
    special_ed_case_id: str
    effective_start: date
    effective_end: Optional[date] = None
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
