from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class StudentGuardianCreate(BaseModel):
    student_id: str
    guardian_id: str
    custody: Optional[str] = None
    is_primary: bool = False
    contact_order: Optional[int] = None


class StudentGuardianOut(ORMBase):
    student_id: str
    guardian_id: str
    custody: Optional[str] = None
    is_primary: bool
    contact_order: Optional[int] = None
    created_at: datetime
    updated_at: datetime
