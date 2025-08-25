from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class ImmunizationRecordCreate(BaseModel):
    student_id: str
    immunization_id: str
    date_administered: date
    dose_number: Optional[int] = None


class ImmunizationRecordOut(ORMBase):
    id: str
    student_id: str
    immunization_id: str
    date_administered: date
    dose_number: Optional[int] = None
    created_at: datetime
    updated_at: datetime
