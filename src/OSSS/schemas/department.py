from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel

from .base import ORMBase


class DepartmentCreate(BaseModel):
    school_id: str
    name: str


class DepartmentOut(ORMBase):
    id: str
    school_id: str
    name: str
    created_at: datetime
    updated_at: datetime
