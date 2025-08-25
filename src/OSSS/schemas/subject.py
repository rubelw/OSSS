from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from pydantic import BaseModel
from .base import ORMBase


class SubjectCreate(BaseModel):
    department_id: Optional[str] = None
    name: str
    code: Optional[str] = None


class SubjectOut(ORMBase):
    id: str
    department_id: Optional[str] = None
    name: str
    code: Optional[str] = None
    created_at: datetime
    updated_at: datetime
