# schemas/project.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from pydantic import BaseModel
from .base import ORMBase


class ProjectCreate(BaseModel):
    school_id: Optional[str] = None
    name: str
    project_type: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget: Optional[Decimal] = None
    description: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class ProjectOut(ORMBase):
    id: str
    school_id: Optional[str] = None
    name: str
    project_type: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget: Optional[Decimal] = None
    description: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
