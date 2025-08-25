from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class NurseVisitCreate(BaseModel):
    student_id: str
    visited_at: datetime
    reason: Optional[str] = None
    disposition: Optional[str] = None


class NurseVisitOut(ORMBase):
    id: str
    student_id: str
    visited_at: datetime
    reason: Optional[str] = None
    disposition: Optional[str] = None
    created_at: datetime
    updated_at: datetime
