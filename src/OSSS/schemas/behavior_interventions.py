from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from .base import ORMBase


class BehaviorInterventionCreate(BaseModel):
    student_id: str = Field(..., description="ID of the student")
    intervention: str = Field(..., min_length=1, description="Description of the intervention")
    start_date: date
    end_date: Optional[date] = None


class BehaviorInterventionOut(ORMBase):
    id: str
    student_id: str
    intervention: str
    start_date: date
    end_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime
