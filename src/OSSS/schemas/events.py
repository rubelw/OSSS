# src/OSSS/schemas/events.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from .base import ORMModel  # ORMBase is aliased to ORMModel in base.py

EventStatus = Literal["draft", "published", "cancelled"]


class EventBase(BaseModel):
    school_id: str
    activity_id: Optional[str] = None

    title: str
    summary: Optional[str] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None
    venue: Optional[str] = None
    status: EventStatus = "draft"
    attributes: Optional[dict] = None

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def _validate_times(self):
        if self.ends_at is not None and self.ends_at < self.starts_at:
            raise ValueError("ends_at must be >= starts_at")
        return self


class EventCreate(EventBase):
    """Payload for creating an event."""
    pass


# --- Backward-compat alias expected by routers ---
EventIn = EventCreate


class EventUpdate(BaseModel):
    """Partial update."""
    school_id: Optional[str] = None
    activity_id: Optional[str] = None

    title: Optional[str] = None
    summary: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    venue: Optional[str] = None
    status: Optional[EventStatus] = None
    attributes: Optional[dict] = None

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def _validate_times(self):
        if self.starts_at and self.ends_at and self.ends_at < self.starts_at:
            raise ValueError("ends_at must be >= starts_at")
        return self


class EventOut(ORMModel):
    id: str
    school_id: str
    activity_id: Optional[str] = None

    title: str
    summary: Optional[str] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None
    venue: Optional[str] = None
    status: EventStatus
    attributes: Optional[dict] = None

    created_at: datetime
    updated_at: datetime


__all__ = [
    "EventStatus",
    "EventBase",
    "EventCreate",
    "EventIn",      # ensure the alias is exported
    "EventUpdate",
    "EventOut",
]
