from __future__ import annotations
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field

from .base import ORMModel


class CICAgendaItemCreate(BaseModel):
    meeting_id: str = Field(..., description="ID of the meeting this item belongs to")
    title: str = Field(..., min_length=1, description="Agenda item title")
    parent_id: Optional[str] = Field(None, description="Parent agenda item ID for nesting")
    position: Optional[int] = Field(
        None, ge=0, description="Order within the agenda; server may set if omitted"
    )
    description: Optional[str] = Field(None, description="Detailed description")
    time_allocated_minutes: Optional[int] = Field(
        None, ge=0, description="Time allocated to this item in minutes"
    )
    subject_id: Optional[str] = Field(None, description="Related subject, if any")
    course_id: Optional[str] = Field(None, description="Related course, if any")


class CICAgendaItemOut(ORMModel):
    id: str
    meeting_id: str
    parent_id: Optional[str] = None
    position: int
    title: str
    description: Optional[str] = None
    time_allocated_minutes: Optional[int] = None
    subject_id: Optional[str] = None
    course_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
