from __future__ import annotations
from typing import Optional
from datetime import datetime

from .base import ORMModel


class CICAgendaItemOut(ORMModel):
    id: str
    meeting_id: str
    parent_id: Optional[str] = None
    position: int
    title: str
    description: Optional[str] = None
    time_allocated_minutes: Optional[int] = None
    subject_id: Optional[str] = None
    course_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
