# OSSS/schemas/family_portal_access.py
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import Field
from OSSS.schemas.base import APIModel

class FamilyPortalAccessBase(APIModel):
    guardian_id: str = Field(...)
    student_id: str = Field(...)
    permissions: Optional[str] = None  # e.g., "view_grades,view_attendance"

class FamilyPortalAccessCreate(FamilyPortalAccessBase):
    pass

class FamilyPortalAccessReplace(FamilyPortalAccessBase):
    pass

class FamilyPortalAccessPatch(APIModel):
    guardian_id: Optional[str] = None
    student_id: Optional[str] = None
    permissions: Optional[str] = None

class FamilyPortalAccessOut(FamilyPortalAccessBase):
    id: str
    created_at: datetime
    updated_at: datetime

class FamilyPortalAccessList(APIModel):
    items: List[FamilyPortalAccessOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
