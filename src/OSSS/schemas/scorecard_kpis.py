# schemas/scorecardkpi.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class ScorecardKPICreate(BaseModel):
    scorecard_id: str
    kpi_id: str
    display_order: Optional[int] = None


class ScorecardKPIOut(ORMBase):
    scorecard_id: str
    kpi_id: str
    display_order: Optional[int] = None
