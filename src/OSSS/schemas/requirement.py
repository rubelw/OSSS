from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, Field

class ReadTimestamps(BaseModel):
    created_at: datetime
    updated_at: datetime

    model_config = dict(from_attributes=True)


class RequirementCreate(BaseModel):
    state_id: UUID
    title: str
    category: Optional[str] = None
    description: Optional[str] = None
    effective_date: Optional[date] = None
    reference_url: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None

class RequirementUpdate(BaseModel):
    state_id: Optional[UUID] = None
    title: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    effective_date: Optional[date] = None
    reference_url: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None

class RequirementRead(ReadTimestamps):
    id: UUID
    state_id: UUID
    title: str
    category: Optional[str] = None
    description: Optional[str] = None
    effective_date: Optional[date] = None
    reference_url: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
