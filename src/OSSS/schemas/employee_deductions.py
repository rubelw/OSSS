from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from pydantic import BaseModel

from .base import ORMBase


class EmployeeDeductionCreate(BaseModel):
    run_id: str
    employee_id: str
    deduction_code_id: str
    amount: Decimal
    attributes: Optional[Dict[str, Any]] = None


class EmployeeDeductionOut(ORMBase):
    id: str
    run_id: str
    employee_id: str
    deduction_code_id: str
    amount: Decimal
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
