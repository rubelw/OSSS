from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class MinutesCreate(BaseModel):
    meeting_id: str
    author_id: Optional[str] = None
    content: Optional[str] = None
    published_at: Optional[datetime] = None


class MinutesOut(ORMBase):
    id: str
    meeting_id: str
    author_id: Optional[str] = None
    content: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
