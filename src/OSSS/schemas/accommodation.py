from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .base import ORMBase


class AccommodationCreate(BaseModel):
    iep_plan_id: Optional[str] = None
    applies_to: Optional[str] = None
    description: str


class AccommodationOut(ORMBase):
    id: str
    iep_plan_id: Optional[str] = None
    applies_to: Optional[str] = None
    description: str
    created_at: datetime
    updated_at: datetime
