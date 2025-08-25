from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class EmergencyContactCreate(BaseModel):
    person_id: str
    contact_name: str
    relationship: Optional[str] = None
    phone: Optional[str] = None


class EmergencyContactOut(ORMBase):
    id: str
    person_id: str
    contact_name: str
    relationship: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime
