from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class StudentCreate(BaseModel):
    student_number: Optional[str] = None
    graduation_year: Optional[int] = None


class StudentOut(ORMBase):
    id: str
    student_number: Optional[str] = None
    graduation_year: Optional[int] = None
    created_at: datetime
    updated_at: datetime
