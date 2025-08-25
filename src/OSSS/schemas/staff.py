from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class StaffCreate(BaseModel):
    employee_number: Optional[str] = None
    title: Optional[str] = None


class StaffOut(ORMBase):
    id: str
    employee_number: Optional[str] = None
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
