from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class GradeLevelCreate(BaseModel):
    school_id: str
    name: str
    ordinal: Optional[int] = None


class GradeLevelOut(ORMBase):
    id: str
    school_id: str
    name: str
    ordinal: Optional[int] = None
    created_at: datetime
    updated_at: datetime
