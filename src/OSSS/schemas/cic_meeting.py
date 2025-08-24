from __future__ import annotations
from typing import Optional
from datetime import datetime

from .base import ORMModel


class CICMeetingOut(ORMModel):
    id: str
    committee_id: str
    title: str
    scheduled_at: datetime
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    status: str
    is_public: bool
    created_at: datetime
    updated_at: datetime
