from __future__ import annotations

from datetime import date
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class KPIDatapointCreate(BaseModel):
    kpi_id: str
    as_of: date
    value: float
    note: Optional[str] = None


class KPIDatapointOut(ORMBase):
    id: str
    kpi_id: str
    as_of: date
    value: float
    note: Optional[str] = None
