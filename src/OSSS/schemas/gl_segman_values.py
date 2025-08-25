from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class GLSegmentValueCreate(BaseModel):
    segment_id: str
    code: str
    name: str
    active: bool = True


class GLSegmentValueUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    active: Optional[bool] = None


class GLSegmentValueOut(ORMBase):
    id: str
    segment_id: str
    code: str
    name: str
    active: bool
    created_at: datetime
    updated_at: datetime
