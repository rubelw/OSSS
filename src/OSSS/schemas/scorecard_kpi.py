# OSSS/schemas/scorecard_kpi.py
from __future__ import annotations
from typing import Optional, List
from pydantic import Field
from OSSS.schemas.base import APIModel

class ScorecardKPIBase(APIModel):
    scorecard_id: str = Field(...)
    kpi_id: str = Field(...)
    display_order: Optional[int] = None

class ScorecardKPICreate(ScorecardKPIBase): pass
class ScorecardKPIReplace(ScorecardKPIBase): pass

class ScorecardKPIPatch(APIModel):
    scorecard_id: Optional[str] = None
    kpi_id: Optional[str] = None
    display_order: Optional[int] = None

class ScorecardKPIOut(ScorecardKPIBase):
    id: str

class ScorecardKPIList(APIModel):
    items: List[ScorecardKPIOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
