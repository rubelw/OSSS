from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class LibraryFineCreate(BaseModel):
    person_id: str
    amount: Decimal
    reason: Optional[str] = None
    assessed_on: Optional[date] = None  # default to "today" server-side if omitted
    paid_on: Optional[date] = None


class LibraryFineOut(ORMBase):
    id: str
    person_id: str
    amount: Decimal
    reason: Optional[str] = None
    assessed_on: date
    paid_on: Optional[date] = None
    created_at: datetime
    updated_at: datetime
