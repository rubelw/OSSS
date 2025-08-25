from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class AttendanceCodeCreate(BaseModel):
    code: str
    description: Optional[str] = None
    is_present: bool = False
    is_excused: bool = False


class AttendanceCodeOut(ORMBase):
    code: str
    description: Optional[str] = None
    is_present: bool
    is_excused: bool
    created_at: datetime
    updated_at: datetime
