from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from pydantic import BaseModel
from .base import ORMBase


class StandardizedTestCreate(BaseModel):
    name: str
    subject: Optional[str] = None


class StandardizedTestOut(ORMBase):
    id: str
    name: str
    subject: Optional[str] = None
    created_at: datetime
    updated_at: datetime
