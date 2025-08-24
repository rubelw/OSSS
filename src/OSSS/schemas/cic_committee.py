from __future__ import annotations
from typing import Optional
from datetime import datetime

from .base import ORMModel


class CICCommitteeOut(ORMModel):
    id: str
    district_id: Optional[str] = None
    school_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
