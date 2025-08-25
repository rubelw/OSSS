from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from .base import ORMModel


class CICMeetingCreate(BaseModel):
    committee_id: str = Field(..., description="Owning committee ID")
    title: str = Field(..., min_length=1, description="Meeting title")
    scheduled_at: datetime = Field(..., description="Start date/time")
    ends_at: Optional[datetime] = Field(None, description="End date/time")
    location: Optional[str] = Field(None, description="Location or URL")
    status: Optional[str] = Field("scheduled", description="scheduled|canceled|completed")
    is_public: Optional[bool] = Field(True, description="Visible to public")


class CICMeetingOut(ORMModel):
    id: str
    committee_id: str
    title: str
    scheduled_at: datetime
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    status: str
    is_public: bool
    created_at: datetime
    updated_at: datetime
