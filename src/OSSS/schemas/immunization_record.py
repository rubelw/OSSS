from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class ImmunizationRecordOut(ORMBase):
    id: str
    student_id: str
    immunization_id: str
    date_administered: date
    dose_number: Optional[int] = None
    created_at: datetime
    updated_at: datetime
