from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class SisImportJobOut(ORMBase):
    id: str
    source: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    counts: Optional[Dict[str, Any]] = None
    error_log: Optional[str] = None
    created_at: datetime
    updated_at: datetime
