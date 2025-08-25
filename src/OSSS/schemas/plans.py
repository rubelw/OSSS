# schemas/plan.py
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class PlanCreate(BaseModel):
    org_id: str
    name: str
    cycle_start: Optional[date] = None
    cycle_end: Optional[date] = None
    status: Optional[str] = None


class PlanOut(ORMBase):
    id: str
    org_id: str
    name: str
    cycle_start: Optional[date] = None
    cycle_end: Optional[date] = None
    status: Optional[str] = None
