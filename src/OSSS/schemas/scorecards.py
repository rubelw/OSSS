# schemas/scorecard.py
from __future__ import annotations

from pydantic import BaseModel
from .base import ORMBase


class ScorecardCreate(BaseModel):
    plan_id: str
    name: str


class ScorecardOut(ORMBase):
    id: str
    plan_id: str
    name: str
