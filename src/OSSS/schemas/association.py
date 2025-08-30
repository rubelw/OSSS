from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, Field

class ReadTimestamps(BaseModel):
    created_at: datetime
    updated_at: datetime

    model_config = dict(from_attributes=True)


class AssociationCreate(BaseModel):
    name: str
    contact: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None

class AssociationUpdate(BaseModel):
    name: Optional[str] = None
    contact: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None

class AssociationRead(ReadTimestamps):
    id: UUID
    name: str
    contact: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None
