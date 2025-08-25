from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field

from .base import ORMBase

class AssignmentCategoryCreate(BaseModel):
    section_id: str
    name: str
    # If weight is used, keep it non-negative (adjust range to your domain, e.g., 0–1 or 0–100)
    weight: Optional[Decimal] = Field(default=None, ge=Decimal("0"))

class AssignmentCategoryOut(ORMBase):
    id: str
    section_id: str
    name: str
    weight: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
