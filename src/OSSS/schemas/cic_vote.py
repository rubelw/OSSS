from __future__ import annotations
from datetime import datetime

from .base import ORMModel


class CICVoteOut(ORMModel):
    id: str
    motion_id: str
    person_id: str
    value: str
    created_at: datetime
    updated_at: datetime
