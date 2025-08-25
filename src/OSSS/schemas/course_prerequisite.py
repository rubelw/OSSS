from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from pydantic import BaseModel  # NEW
from .base import ORMBase


class CoursePrerequisiteCreate(BaseModel):
    course_id: str
    prereq_course_id: str


class CoursePrerequisiteOut(ORMBase):
    course_id: str
    prereq_course_id: str
    created_at: datetime
    updated_at: datetime
