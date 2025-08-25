from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class MeetingFileCreate(BaseModel):
    meeting_id: str
    file_id: str
    caption: Optional[str] = None


class MeetingFileOut(ORMBase):
    meeting_id: str
    file_id: str
    caption: Optional[str] = None
