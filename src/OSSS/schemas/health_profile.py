from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class HealthProfileCreate(BaseModel):
    student_id: str
    allergies: Optional[str] = None
    conditions: Optional[str] = None


class HealthProfileOut(ORMBase):
    id: str
    student_id: str
    allergies: Optional[str] = None
    conditions: Optional[str] = None
    created_at: datetime
    updated_at: datetime
