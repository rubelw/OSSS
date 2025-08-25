from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class ObjectiveCreate(BaseModel):
    goal_id: str
    name: str
    description: Optional[str] = None


class ObjectiveOut(ORMBase):
    id: str
    goal_id: str
    name: str
    description: Optional[str] = None
