from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class GoalCreate(BaseModel):
    plan_id: str
    name: str
    description: Optional[str] = None


class GoalOut(ORMBase):
    id: str
    plan_id: str
    name: str
    description: Optional[str] = None
