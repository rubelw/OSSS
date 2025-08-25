from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class MeetingSearchIndexCreate(BaseModel):
    meeting_id: str
    ts: Optional[str] = None


class MeetingSearchIndexOut(ORMBase):
    meeting_id: str
    ts: Optional[str] = None
