from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict
from pydantic import BaseModel

from .base import ORMBase


class GpaCalculationCreate(BaseModel):
    student_id: str
    term_id: str
    gpa: Decimal


class GpaCalculationOut(ORMBase):
    id: str
    student_id: str
    term_id: str
    gpa: Decimal
    created_at: datetime
    updated_at: datetime
