# schemas/workordertimeLog.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class WorkOrderTimeLogCreate(BaseModel):
    work_order_id: str
    user_id: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    hours: Optional[Decimal] = None
    hourly_rate: Optional[Decimal] = None
    cost: Optional[Decimal] = None
    notes: Optional[str] = None


class WorkOrderTimeLogOut(ORMBase):
    id: str
    work_order_id: str
    user_id: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    hours: Optional[Decimal] = None
    hourly_rate: Optional[Decimal] = None
    cost: Optional[Decimal] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
