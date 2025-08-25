from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class CourseCreate(BaseModel):
    school_id: str
    name: str
    subject_id: Optional[str] = None
    code: Optional[str] = None
    credit_hours: Optional[Decimal] = None


class CourseOut(ORMBase):
    id: str
    school_id: str
    subject_id: Optional[str] = None
    name: str
    code: Optional[str] = None
    credit_hours: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
