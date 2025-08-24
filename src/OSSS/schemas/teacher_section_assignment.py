from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class TeacherSectionAssignmentOut(ORMBase):
    id: str
    staff_id: str
    section_id: str
    role: Optional[str] = None
    created_at: datetime
    updated_at: datetime
