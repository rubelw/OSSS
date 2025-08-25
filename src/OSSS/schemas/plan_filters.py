# schemas/planfilter.py
from __future__ import annotations

from typing import Optional, Dict, Any

from pydantic import BaseModel
from .base import ORMBase


class PlanFilterCreate(BaseModel):
    plan_id: str
    name: str
    criteria: Optional[Dict[str, Any]] = None


class PlanFilterOut(ORMBase):
    id: str
    plan_id: str
    name: str
    criteria: Optional[Dict[str, Any]] = None
