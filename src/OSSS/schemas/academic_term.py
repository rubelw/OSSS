# src/OSSS/schemas/academic_term.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from .base import ORMBase

class AcademicTermCreate(ORMBase):
    school_id: UUID          # accepts string UUIDs in requests; Pydantic parses to UUID
    name: str
    type: Optional[str] = None
    start_date: date
    end_date: date

class AcademicTermOut(ORMBase):
    id: UUID                 # <-- changed from str
    school_id: UUID          # <-- changed from str
    name: str
    type: Optional[str] = None
    start_date: date
    end_date: date
    created_at: datetime
    updated_at: datetime
