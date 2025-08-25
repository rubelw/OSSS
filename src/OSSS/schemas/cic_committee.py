from __future__ import annotations
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from .base import ORMModel


class CICCommitteeCreate(BaseModel):
    district_id: Optional[str] = Field(None, description="Owning district, if applicable")
    school_id: Optional[str] = Field(None, description="Owning school, if applicable")
    name: str = Field(..., min_length=1, description="Committee name")
    description: Optional[str] = Field(None, description="Short description")
    status: Optional[str] = Field("active", description="Status (e.g., active, inactive)")


class CICCommitteeOut(ORMModel):
    id: str
    district_id: Optional[str] = None
    school_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
