from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class SpecialEducationCaseCreate(BaseModel):
    student_id: str
    eligibility: Optional[str] = None
    case_opened: Optional[date] = None
    case_closed: Optional[date] = None


class SpecialEducationCaseOut(ORMBase):
    id: str
    student_id: str
    eligibility: Optional[str] = None
    case_opened: Optional[date] = None
    case_closed: Optional[date] = None
    created_at: datetime
    updated_at: datetime
