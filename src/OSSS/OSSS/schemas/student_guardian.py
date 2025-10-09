# OSSS/schemas/student_guardian.py
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import Field
from OSSS.schemas.base import APIModel

class StudentGuardianBase(APIModel):
    student_id: str = Field(...)
    guardian_id: str = Field(...)
    custody: Optional[str] = None
    is_primary: Optional[bool] = None
    contact_order: Optional[int] = None

class StudentGuardianCreate(StudentGuardianBase):
    pass

class StudentGuardianReplace(StudentGuardianBase):
    # make booleans explicit if you prefer
    is_primary: bool = Field(...)

class StudentGuardianPatch(APIModel):
    student_id: Optional[str] = None
    guardian_id: Optional[str] = None
    custody: Optional[str] = None
    is_primary: Optional[bool] = None
    contact_order: Optional[int] = None

class StudentGuardianOut(StudentGuardianBase):
    id: str
    created_at: datetime
    updated_at: datetime

class StudentGuardianList(APIModel):
    items: List[StudentGuardianOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
