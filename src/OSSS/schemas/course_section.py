from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict
from pydantic import BaseModel

from .base import ORMBase


class CourseSectionCreate(BaseModel):
    course_id: str
    term_id: str
    section_number: str
    school_id: str
    capacity: Optional[int] = None


class CourseSectionOut(ORMBase):
    id: str
    course_id: str
    term_id: str
    section_number: str
    capacity: Optional[int] = None
    school_id: str
    created_at: datetime
    updated_at: datetime
