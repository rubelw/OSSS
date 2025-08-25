from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class ImmunizationCreate(BaseModel):
    name: str
    code: Optional[str] = None


class ImmunizationOut(ORMBase):
    id: str
    name: str
    code: Optional[str] = None
    created_at: datetime
    updated_at: datetime
