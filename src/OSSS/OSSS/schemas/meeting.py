from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, AliasChoices, ConfigDict, model_validator


class MeetingBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    org_id: uuid.UUID = Field(..., description="FK to organizations.id")

    # Keep legacy alias 'body_id' → governing_body_id (drop 'committee_id' alias)
    governing_body_id: Optional[uuid.UUID] = Field(
        default=None,
        validation_alias=AliasChoices("governing_body_id", "body_id"),
        description="FK to governing_bodies.id (legacy input alias accepted: body_id).",
    )

    # NEW: real committee FK (matches SQLA: NOT NULL)
    # Declare Optional here so MeetingOut/Update can reuse the base;
    # MeetingCreate narrows this to a required uuid.UUID.
    committee_id: Optional[uuid.UUID] = Field(
        default=None,
        description="FK to committees.id.",
    )

    title: str = Field(..., max_length=255)
    scheduled_at: datetime = Field(..., description="Planned start datetime (tz-aware).")
    starts_at: datetime = Field(..., description="Actual start datetime (tz-aware).")
    ends_at: Optional[datetime] = Field(
        None, description="Actual end datetime (tz-aware), must be >= starts_at when present."
    )
    location: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, max_length=32)
    is_public: bool = Field(True, description="Whether the meeting is public.")
    stream_url: Optional[str] = Field(None, max_length=1024)

    @model_validator(mode="after")
    def _validate_times(self) -> "MeetingBase":
        if self.ends_at and self.starts_at and self.ends_at < self.starts_at:
            raise ValueError("ends_at must be greater than or equal to starts_at")
        if self.scheduled_at and self.starts_at and self.starts_at < self.scheduled_at:
            # Optional: enforce starts_at is not before planned start
            raise ValueError("starts_at must be greater than or equal to scheduled_at")
        return self


class MeetingCreate(MeetingBase):
    # Allow scheduled_at to be omitted; default it to starts_at for convenience
    scheduled_at: Optional[datetime] = Field(
        None, description="If omitted, defaults to starts_at."
    )

    # committee_id is REQUIRED on create (SQLA nullable=False)
    committee_id: uuid.UUID = Field(..., description="FK to committees.id (required).")

    @model_validator(mode="after")
    def _default_scheduled_at(self) -> "MeetingCreate":
        if self.scheduled_at is None and self.starts_at is not None:
            object.__setattr__(self, "scheduled_at", self.starts_at)
        return self


class MeetingUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    org_id: Optional[uuid.UUID] = None
    governing_body_id: Optional[uuid.UUID] = Field(
        default=None,
        validation_alias=AliasChoices("governing_body_id", "body_id"),
        description="FK to governing_bodies.id (legacy input alias accepted: body_id).",
    )
    committee_id: Optional[uuid.UUID] = Field(
        default=None, description="FK to committees.id."
    )

    title: Optional[str] = Field(None, max_length=255)
    scheduled_at: Optional[datetime] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, max_length=32)
    is_public: Optional[bool] = None
    stream_url: Optional[str] = Field(None, max_length=1024)

    @model_validator(mode="after")
    def _validate_times(self) -> "MeetingUpdate":
        if self.ends_at and self.starts_at and self.ends_at < self.starts_at:
            raise ValueError("ends_at must be greater than or equal to starts_at")
        if self.scheduled_at and self.starts_at and self.starts_at < self.scheduled_at:
            raise ValueError("starts_at must be greater than or equal to scheduled_at")
        return self


class MeetingOut(MeetingBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
