from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict
from pydantic import BaseModel

from .base import ORMBase


class DataQualityIssueCreate(BaseModel):
    entity_type: str
    entity_id: str
    rule: str
    severity: str
    details: Optional[str] = None
    detected_at: Optional[datetime] = None  # server can default to now


class DataQualityIssueOut(ORMBase):
    id: str
    entity_type: str
    entity_id: str
    rule: str
    severity: str
    details: Optional[str] = None
    detected_at: datetime
    created_at: datetime
    updated_at: datetime
