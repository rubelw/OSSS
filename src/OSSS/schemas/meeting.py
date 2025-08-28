# OSSS/schemas/meeting.py
from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from pydantic import Field

from OSSS.schemas.base import APIModel


# -----------------------------
# Base (shared fields)
# -----------------------------
class MeetingBase(APIModel):
    org_id: str = Field(..., description="Organization UUID")
    body_id: Optional[str] = Field(None, description="Body UUID (nullable)")
    title: str = Field(..., max_length=255)
    starts_at: datetime = Field(..., description="Start timestamp (TZ-aware)")
    ends_at: Optional[datetime] = Field(None, description="End timestamp (TZ-aware)")
    location: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, max_length=32)
    # server_default true in the DB; keep optional here so API can omit and let DB default apply
    is_public: Optional[bool] = Field(None, description="If omitted, defaults to true in DB")
    stream_url: Optional[str] = Field(None, max_length=1024)


# -----------------------------
# Create (POST)
# -----------------------------
class MeetingCreate(MeetingBase):
    # Nothing extra; leaving is_public optional allows DB default to kick in
    pass


# -----------------------------
# Replace (PUT)
# -----------------------------
class MeetingReplace(MeetingBase):
    # PUT = full replacement; still mirrors Base types
    # If you prefer to require is_public on PUT, change to: is_public: bool = Field(...)
    pass


# -----------------------------
# Patch (PATCH)
# -----------------------------
class MeetingPatch(APIModel):
    org_id: Optional[str] = None
    body_id: Optional[str] = None
    title: Optional[str] = Field(None, max_length=255)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, max_length=32)
    is_public: Optional[bool] = None
    stream_url: Optional[str] = Field(None, max_length=1024)


# -----------------------------
# Read (GET)
# -----------------------------
class MeetingOut(MeetingBase):
    id: str
    created_at: datetime
    updated_at: datetime

    # If you want lightweight relationship summaries without importing child schemas,
    # uncomment these count fields:
    # agenda_items_count: Optional[int] = None
    # minutes_count: Optional[int] = None
    # files_count: Optional[int] = None
    # attendance_count: Optional[int] = None


# -----------------------------
# List wrapper
# -----------------------------
class MeetingList(APIModel):
    items: List[MeetingOut]
    total: Optional[int] = None
    skip: int = 0
    limit: int = 100


# -----------------------------
# Back-compat aliases (if your generator expects these names)
# -----------------------------
MeetingRead = MeetingOut
MeetingPut = MeetingReplace
MeetingUpdate = MeetingPatch
MeetingIn = MeetingCreate

__all__ = [
    "MeetingBase",
    "MeetingCreate",
    "MeetingReplace",
    "MeetingPatch",
    "MeetingOut",
    "MeetingList",
    # aliases
    "MeetingRead",
    "MeetingPut",
    "MeetingUpdate",
    "MeetingIn",
]
