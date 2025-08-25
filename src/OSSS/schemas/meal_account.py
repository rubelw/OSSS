from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict
from pydantic import BaseModel

from .base import ORMBase


class MealAccountCreate(BaseModel):
    student_id: str
    balance: Decimal = Decimal("0.00")


class MealAccountOut(ORMBase):
    id: str
    student_id: str
    balance: Decimal
    created_at: datetime
    updated_at: datetime
