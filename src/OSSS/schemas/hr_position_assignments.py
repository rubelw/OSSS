from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from .base import ORMBase


class HRPositionAssignmentCreate(BaseModel):
    employee_id: str
    position_id: str
    start_date: date
    end_date: Optional[date] = None
    percent: Optional[Decimal] = None               # allocation percent (e.g., 50.00)
    funding_split: Optional[List[Dict[str, Any]]] = None  # [{gl_account_id, percent}, ...]


class HRPositionAssignmentOut(ORMBase):
    id: str
    employee_id: str
    position_id: str
    start_date: date
    end_date: Optional[date] = None
    percent: Optional[Decimal] = None
    funding_split: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    updated_at: datetime
