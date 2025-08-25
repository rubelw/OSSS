from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class MedicationCreate(BaseModel):
    name: str
    instructions: Optional[str] = None


class MedicationOut(ORMBase):
    id: str
    name: str
    instructions: Optional[str] = None
    created_at: datetime
    updated_at: datetime
