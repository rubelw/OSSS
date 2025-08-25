# schemas/workordertask.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class WorkOrderTaskCreate(BaseModel):
    work_order_id: str
    seq: int = 1
    title: str
    is_mandatory: bool = False
    status: Optional[str] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None


class WorkOrderTaskOut(ORMBase):
    id: str
    work_order_id: str
    seq: int
    title: str
    is_mandatory: bool
    status: Optional[str] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
