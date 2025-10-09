from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, Field

class ReadTimestamps(BaseModel):
    created_at: datetime
    updated_at: datetime

    model_config = dict(from_attributes=True)


class CurriculumVersionCreate(BaseModel):
    curriculum_id: UUID
    version: str
    status: Optional[str] = "draft"
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    notes: Optional[str] = None

class CurriculumVersionUpdate(BaseModel):
    curriculum_id: Optional[UUID] = None
    version: Optional[str] = None
    status: Optional[str] = None
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    notes: Optional[str] = None

class CurriculumVersionRead(ReadTimestamps):
    id: UUID
    curriculum_id: UUID
    version: str
    status: str
    submitted_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    notes: Optional[str] = None
