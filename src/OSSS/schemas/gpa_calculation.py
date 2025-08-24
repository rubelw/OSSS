from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class GpaCalculationOut(ORMBase):
    id: str
    student_id: str
    term_id: str
    gpa: Decimal
    created_at: datetime
    updated_at: datetime
