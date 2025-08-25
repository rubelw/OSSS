from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class StudentTransportationAssignmentCreate(BaseModel):
    student_id: str
    route_id: Optional[str] = None
    stop_id: Optional[str] = None
    direction: Optional[str] = None
    effective_start: date
    effective_end: Optional[date] = None


class StudentTransportationAssignmentOut(ORMBase):
    id: str
    student_id: str
    route_id: Optional[str] = None
    stop_id: Optional[str] = None
    direction: Optional[str] = None
    effective_start: date
    effective_end: Optional[date] = None
    created_at: datetime
    updated_at: datetime
