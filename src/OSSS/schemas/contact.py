from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from pydantic import BaseModel  # NEW

from .base import ORMBase


class ContactCreate(BaseModel):
    type: str
    value: str


class ContactOut(ORMBase):
    id: str
    type: str
    value: str
    created_at: datetime
    updated_at: datetime
