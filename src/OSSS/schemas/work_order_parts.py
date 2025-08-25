# schemas/workorderpart.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class WorkOrderPartCreate(BaseModel):
    work_order_id: str
    part_id: Optional[str] = None
    qty: Decimal = Decimal("1")
    unit_cost: Optional[Decimal] = None
    extended_cost: Optional[Decimal] = None
    notes: Optional[str] = None


class WorkOrderPartOut(ORMBase):
    id: str
    work_order_id: str
    part_id: Optional[str] = None
    qty: Decimal
    unit_cost: Optional[Decimal] = None
    extended_cost: Optional[Decimal] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
