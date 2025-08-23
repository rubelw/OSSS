from __future__ import annotations
from typing import Optional, List
from datetime import datetime

from .base import ORMModel, TimestampMixin


class MeetingBase(ORMModel):
    org_id: str
    title: str
    starts_at: datetime
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    status: Optional[str] = None
    is_public: bool = True
    body_id: Optional[str] = None
    stream_url: Optional[str] = None


class MeetingCreate(MeetingBase):
    pass


class MeetingOut(MeetingBase, TimestampMixin):
    id: str


class AgendaItemBase(ORMModel):
    meeting_id: str
    title: str
    parent_id: Optional[str] = None
    position: int = 0
    description: Optional[str] = None
    linked_policy_id: Optional[str] = None
    linked_objective_id: Optional[str] = None
    time_allocated: Optional[int] = None


class AgendaItemCreate(AgendaItemBase):
    pass


class AgendaItemOut(AgendaItemBase):
    id: str


class MinutesOut(ORMModel, TimestampMixin):
    id: str
    meeting_id: str
    author_id: Optional[str] = None
    content: Optional[str] = None
    published_at: Optional[datetime] = None
