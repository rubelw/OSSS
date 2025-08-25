from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel
from .base import ORMBase


class StateReportingSnapshotCreate(BaseModel):
    as_of_date: date
    scope: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class StateReportingSnapshotOut(ORMBase):
    id: str
    as_of_date: date
    scope: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
