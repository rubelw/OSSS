# schemas/consequence.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from .base import ORMBase


class ConsequenceCreate(BaseModel):
    incident_id: str
    participant_id: str
    consequence_code: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None


class ConsequenceOut(ORMBase):
    id: str
    incident_id: str
    participant_id: str
    consequence_code: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
