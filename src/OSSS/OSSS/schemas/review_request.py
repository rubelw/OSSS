from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, Field

class ReadTimestamps(BaseModel):
    created_at: datetime
    updated_at: datetime

    model_config = dict(from_attributes=True)


class ReviewRequestCreate(BaseModel):
    curriculum_version_id: UUID
    association_id: UUID
    status: Optional[str] = "submitted"
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    notes: Optional[str] = None

class ReviewRequestUpdate(BaseModel):
    curriculum_version_id: Optional[UUID] = None
    association_id: Optional[UUID] = None
    status: Optional[str] = None
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    notes: Optional[str] = None

class ReviewRequestRead(ReadTimestamps):
    id: UUID
    curriculum_version_id: UUID
    association_id: UUID
    status: str
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    notes: Optional[str] = None
