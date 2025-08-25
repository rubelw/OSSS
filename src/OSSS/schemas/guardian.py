from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class GuardianCreate(BaseModel):
    # Link the guardian (person) to a student and optionally describe the relationship
    person_id: str
    student_id: str
    relationship: Optional[str] = None
    is_primary: Optional[bool] = False


class GuardianOut(ORMBase):
    id: str
    relationship: Optional[str] = None
    created_at: datetime
    updated_at: datetime
