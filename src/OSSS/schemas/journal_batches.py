from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class JournalBatchCreate(BaseModel):
    batch_no: str
    description: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = "open"  # open | posted
    posted_at: Optional[datetime] = None


class JournalBatchOut(ORMBase):
    id: str
    batch_no: str
    description: Optional[str] = None
    source: Optional[str] = None
    status: str
    posted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
