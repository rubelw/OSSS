from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class TestResultCreate(BaseModel):
    administration_id: str
    student_id: str
    scale_score: Optional[Decimal] = None
    percentile: Optional[Decimal] = None
    performance_level: Optional[str] = None


class TestResultOut(ORMBase):
    id: str
    administration_id: str
    student_id: str
    scale_score: Optional[Decimal] = None
    percentile: Optional[Decimal] = None
    performance_level: Optional[str] = None
    created_at: datetime
    updated_at: datetime
