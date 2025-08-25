from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class ReportCardCreate(BaseModel):
    student_id: str
    term_id: str
    published_at: Optional[datetime] = None


class ReportCardOut(ORMBase):
    id: str
    student_id: str
    term_id: str
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
