from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class LibraryHoldCreate(BaseModel):
    item_id: str
    person_id: str
    placed_on: Optional[date] = None  # set to today server-side if omitted
    expires_on: Optional[date] = None


class LibraryHoldOut(ORMBase):
    id: str
    item_id: str
    person_id: str
    placed_on: date
    expires_on: Optional[date] = None
    created_at: datetime
    updated_at: datetime
