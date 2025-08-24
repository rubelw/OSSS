from __future__ import annotations
from typing import Optional
from datetime import datetime, date

from .base import ORMModel


class CICResolutionOut(ORMModel):
    id: str
    meeting_id: str
    title: str
    summary: Optional[str] = None
    effective_date: Optional[date] = None
    status: Optional[str] = None
    created_at: datetime
    updated_at: datetime
