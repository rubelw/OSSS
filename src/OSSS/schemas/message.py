from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class MessageCreate(BaseModel):
    sender_id: Optional[str] = None
    channel: str
    subject: Optional[str] = None
    body: Optional[str] = None
    sent_at: Optional[datetime] = None


class MessageOut(ORMBase):
    id: str
    sender_id: Optional[str] = None
    channel: str
    subject: Optional[str] = None
    body: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
