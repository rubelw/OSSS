from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class InvoiceCreate(BaseModel):
    student_id: str
    issued_on: date
    due_on: Optional[date] = None
    status: Optional[str] = "draft"


class InvoiceOut(ORMBase):
    id: str
    student_id: str
    issued_on: date
    due_on: Optional[date] = None
    status: str
    created_at: datetime
    updated_at: datetime
