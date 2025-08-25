from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class GradeScaleCreate(BaseModel):
    school_id: str
    name: str
    type: Optional[str] = None  # e.g., letter, numeric


class GradeScaleOut(ORMBase):
    id: str
    school_id: str
    name: str
    type: Optional[str] = None
    created_at: datetime
    updated_at: datetime
