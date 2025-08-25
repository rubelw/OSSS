from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class KPICreate(BaseModel):
    goal_id: Optional[str] = None
    objective_id: Optional[str] = None
    name: str
    unit: Optional[str] = None
    target: Optional[float] = None
    baseline: Optional[float] = None
    direction: Optional[str] = None  # "up" | "down"


class KPIOut(ORMBase):
    id: str
    goal_id: Optional[str] = None
    objective_id: Optional[str] = None
    name: str
    unit: Optional[str] = None
    target: Optional[float] = None
    baseline: Optional[float] = None
    direction: Optional[str] = None
