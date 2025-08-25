from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class LibraryCheckoutCreate(BaseModel):
    item_id: str
    person_id: str
    checked_out_on: Optional[date] = None
    due_on: Optional[date] = None
    returned_on: Optional[date] = None


class LibraryCheckoutOut(ORMBase):
    id: str
    item_id: str
    person_id: str
    checked_out_on: date
    due_on: date
    returned_on: Optional[date] = None
    created_at: datetime
    updated_at: datetime
