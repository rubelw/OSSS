# schemas/planalignment.py
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class PlanAlignmentCreate(BaseModel):
    agenda_item_id: Optional[str] = None
    policy_id: Optional[str] = None
    objective_id: Optional[str] = None
    note: Optional[str] = None


class PlanAlignmentOut(ORMBase):
    id: str
    agenda_item_id: Optional[str] = None
    policy_id: Optional[str] = None
    objective_id: Optional[str] = None
    note: Optional[str] = None
