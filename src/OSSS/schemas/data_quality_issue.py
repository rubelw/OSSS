from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

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
