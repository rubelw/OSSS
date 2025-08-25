from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class FamilyPortalAccessCreate(BaseModel):
    guardian_id: str
    student_id: str
    permissions: Optional[str] = None


class FamilyPortalAccessOut(ORMBase):
    guardian_id: str
    student_id: str
    permissions: Optional[str] = None
    created_at: datetime
    updated_at: datetime
