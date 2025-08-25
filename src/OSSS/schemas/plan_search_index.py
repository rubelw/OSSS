# schemas/plansearchindex.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class PlanSearchIndexCreate(BaseModel):
    plan_id: str
    ts: Optional[str] = None


class PlanSearchIndexOut(ORMBase):
    plan_id: str
    ts: Optional[str] = None
