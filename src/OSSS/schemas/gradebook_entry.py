from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class GradebookEntryCreate(BaseModel):
    assignment_id: str
    student_id: str
    score: Optional[Decimal] = None
    submitted_at: Optional[datetime] = None
    late: Optional[bool] = False


class GradebookEntryOut(ORMBase):
    id: str
    assignment_id: str
    student_id: str
    score: Optional[Decimal] = None
    submitted_at: Optional[datetime] = None
    late: bool
    created_at: datetime
    updated_at: datetime
