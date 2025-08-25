from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class MeetingPublicationCreate(BaseModel):
    meeting_id: str
    published_at: datetime
    public_url: Optional[str] = None
    archive_url: Optional[str] = None


class MeetingPublicationOut(ORMBase):
    meeting_id: str
    published_at: datetime
    public_url: Optional[str] = None
    archive_url: Optional[str] = None
