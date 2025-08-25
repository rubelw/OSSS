# schemas/consent.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from .base import ORMBase


class ConsentCreate(BaseModel):
    person_id: str
    consent_type: str
    granted: bool
    effective_date: date
    expires_on: Optional[date] = None


class ConsentOut(ORMBase):
    id: str
    person_id: str
    consent_type: str
    granted: bool
    effective_date: date
    expires_on: Optional[date] = None
    created_at: datetime
    updated_at: datetime
