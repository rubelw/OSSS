from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, Field

class ReadTimestamps(BaseModel):
    created_at: datetime
    updated_at: datetime

    model_config = dict(from_attributes=True)


class AlignmentCreate(BaseModel):
    curriculum_version_id: UUID
    requirement_id: UUID
    alignment_level: Optional[str] = "unknown"
    evidence_url: Optional[str] = None
    notes: Optional[str] = None

class AlignmentUpdate(BaseModel):
    curriculum_version_id: Optional[UUID] = None
    requirement_id: Optional[UUID] = None
    alignment_level: Optional[str] = None
    evidence_url: Optional[str] = None
    notes: Optional[str] = None

class AlignmentRead(ReadTimestamps):
    id: UUID
    curriculum_version_id: UUID
    requirement_id: UUID
    alignment_level: str
    evidence_url: Optional[str] = None
    notes: Optional[str] = None
