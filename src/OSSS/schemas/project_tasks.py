# schemas/projecttask.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from pydantic import BaseModel
from .base import ORMBase


class ProjectTaskCreate(BaseModel):
    project_id: str
    name: str
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    percent_complete: Optional[Decimal] = None
    assignee_user_id: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class ProjectTaskOut(ORMBase):
    id: str
    project_id: str
    name: str
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    percent_complete: Optional[Decimal] = None
    assignee_user_id: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
