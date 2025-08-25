from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


from .base import ORMBase

class AssignmentCreate(BaseModel):
    section_id: str
    name: str
    category_id: Optional[str] = None
    due_date: Optional[date] = None
    points_possible: Optional[Decimal] = Field(default=None, ge=Decimal("0"))

class AssignmentOut(ORMBase):
    id: str
    section_id: str
    category_id: Optional[str] = None
    name: str
    due_date: Optional[date] = None
    points_possible: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
