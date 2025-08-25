from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class MedicationAdministrationCreate(BaseModel):
    student_id: str
    medication_id: str
    administered_at: Optional[datetime] = None  # set by client or server
    dose: Optional[str] = None
    notes: Optional[str] = None


class MedicationAdministrationOut(ORMBase):
    id: str
    student_id: str
    medication_id: str
    administered_at: datetime
    dose: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
