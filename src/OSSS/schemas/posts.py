# schemas/post.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class PostCreate(BaseModel):
    channel_id: str
    title: str
    body: Optional[str] = None
    status: str = "draft"  # draft | scheduled | published
    publish_at: Optional[datetime] = None
    author_id: Optional[str] = None


class PostOut(ORMBase):
    id: str
    channel_id: str
    title: str
    body: Optional[str] = None
    status: str
    publish_at: Optional[datetime] = None
    author_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
