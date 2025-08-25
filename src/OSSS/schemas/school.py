from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from pydantic import BaseModel
from .base import ORMBase


class SchoolCreate(BaseModel):
    district_id: str
    name: str
    school_code: Optional[str] = None
    nces_school_id: Optional[str] = None
    building_code: Optional[str] = None
    type: Optional[str] = None
    timezone: Optional[str] = None


class SchoolOut(ORMBase):
    id: str
    district_id: str
    name: str
    school_code: Optional[str] = None
    nces_school_id: Optional[str] = None
    building_code: Optional[str] = None
    type: Optional[str] = None
    timezone: Optional[str] = None
    created_at: datetime
    updated_at: datetime
