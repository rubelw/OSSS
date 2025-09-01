from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, Field

class ReadTimestamps(BaseModel):
    created_at: datetime
    updated_at: datetime

    model_config = dict(from_attributes=True)


class CurriculumCreate(BaseModel):
    district_id: UUID
    title: str
    subject: Optional[str] = None
    grade_range: Optional[str] = None
    description: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None

class CurriculumUpdate(BaseModel):
    district_id: Optional[UUID] = None
    title: Optional[str] = None
    subject: Optional[str] = None
    grade_range: Optional[str] = None
    description: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None

class CurriculumRead(ReadTimestamps):
    id: UUID
    district_id: UUID
    title: str
    subject: Optional[str] = None
    grade_range: Optional[str] = None
    description: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
