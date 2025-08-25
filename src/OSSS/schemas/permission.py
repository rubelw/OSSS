from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from pydantic import BaseModel
from .base import ORMBase


class PermissionCreate(BaseModel):
    code: str
    description: Optional[str] = None


class PermissionOut(ORMBase):
    id: str
    code: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
