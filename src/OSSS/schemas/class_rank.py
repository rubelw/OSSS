from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class ClassRankOut(ORMBase):
    id: str
    school_id: str
    term_id: str
    student_id: str
    rank: int
    created_at: datetime
    updated_at: datetime
