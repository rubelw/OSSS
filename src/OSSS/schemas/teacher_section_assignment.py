from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class TeacherSectionAssignmentCreate(BaseModel):
    staff_id: str
    section_id: str
    role: Optional[str] = None


class TeacherSectionAssignmentOut(ORMBase):
    id: str
    staff_id: str
    section_id: str
    role: Optional[str] = None
    created_at: datetime
    updated_at: datetime
