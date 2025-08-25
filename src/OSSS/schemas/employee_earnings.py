from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class EmployeeEarningCreate(BaseModel):
    run_id: str
    employee_id: str
    earning_code_id: str
    hours: Optional[Decimal] = None
    rate: Optional[Decimal] = None
    amount: Decimal


class EmployeeEarningOut(ORMBase):
    id: str
    run_id: str
    employee_id: str
    earning_code_id: str
    hours: Optional[Decimal] = None
    rate: Optional[Decimal] = None
    amount: Decimal
    created_at: datetime
    updated_at: datetime
