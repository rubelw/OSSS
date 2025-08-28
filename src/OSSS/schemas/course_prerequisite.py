# OSSS/schemas/course_prerequisite.py
from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from pydantic import Field
from OSSS.schemas.base import APIModel

class CoursePrereqBase(APIModel):
    course_id: str = Field(...)
    prereq_course_id: str = Field(...)

class CoursePrereqCreate(CoursePrereqBase): pass
class CoursePrereqReplace(CoursePrereqBase): pass

class CoursePrereqPatch(APIModel):
    course_id: Optional[str] = None
    prereq_course_id: Optional[str] = None

class CoursePrereqOut(CoursePrereqBase):
    id: str
    created_at: datetime
    updated_at: datetime

class CoursePrereqList(APIModel):
    items: List[CoursePrereqOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
