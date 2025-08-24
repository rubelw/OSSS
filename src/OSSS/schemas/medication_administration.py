from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class MedicationAdministrationOut(ORMBase):
    id: str
    student_id: str
    medication_id: str
    administered_at: datetime
    dose: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
