from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class WaiverCreate(BaseModel):
    student_id: str
    reason: Optional[str] = None
    amount: Optional[Decimal] = None
    granted_on: Optional[date] = None


class WaiverOut(ORMBase):
    id: str
    student_id: str
    reason: Optional[str] = None
    amount: Optional[Decimal] = None
    granted_on: Optional[date] = None
    created_at: datetime
    updated_at: datetime
