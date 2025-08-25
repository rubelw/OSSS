from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class PageCreate(BaseModel):
    channel_id: str
    slug: str
    title: str
    body: Optional[str] = None
    status: Optional[str] = None  # 'draft'|'published' etc. (defaults to 'draft' in DB)
    published_at: Optional[datetime] = None


class PageOut(ORMBase):
    id: str
    channel_id: str
    slug: str
    title: str
    body: Optional[str] = None
    status: str
    published_at: Optional[datetime] = None
