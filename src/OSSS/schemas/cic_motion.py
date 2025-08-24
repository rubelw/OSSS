from __future__ import annotations
from typing import Optional
from datetime import datetime

from .base import ORMModel


class CICMotionOut(ORMModel):
    id: str
    agenda_item_id: str
    text: str
    moved_by_id: Optional[str] = None
    seconded_by_id: Optional[str] = None
    result: Optional[str] = None
    tally_for: Optional[int] = None
    tally_against: Optional[int] = None
    tally_abstain: Optional[int] = None
    created_at: datetime
    updated_at: datetime
