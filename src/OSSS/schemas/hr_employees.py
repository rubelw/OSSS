from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel

from .base import ORMBase


class HREmployeeCreate(BaseModel):
    person_id: Optional[str] = None
    employee_no: str
    primary_school_id: Optional[str] = None
    department_segment_id: Optional[str] = None  # GL segment (not value)
    employment_type: Optional[str] = None        # full_time | part_time | etc.
    status: Optional[str] = "active"
    hire_date: Optional[date] = None
    termination_date: Optional[date] = None
    attributes: Optional[Dict[str, Any]] = None


class HREmployeeOut(ORMBase):
    id: str
    person_id: Optional[str] = None
    employee_no: str
    primary_school_id: Optional[str] = None
    department_segment_id: Optional[str] = None
    employment_type: Optional[str] = None
    status: str
    hire_date: Optional[date] = None
    termination_date: Optional[date] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
