from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class GLAccountSegmentCreate(BaseModel):
    account_id: str
    segment_id: str
    position: int


class GLAccountSegmentUpdate(BaseModel):
    # Make fields optional to support PATCH-style updates
    account_id: Optional[str] = None
    segment_id: Optional[str] = None
    position: Optional[int] = None


class GLAccountSegmentOut(ORMBase):
    id: str
    account_id: str
    segment_id: str
    position: int
    created_at: datetime
    updated_at: datetime
