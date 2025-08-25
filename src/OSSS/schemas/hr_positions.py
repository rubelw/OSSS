from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from pydantic import BaseModel

from .base import ORMBase


class HRPositionCreate(BaseModel):
    title: str
    department_segment_id: Optional[str] = None  # GL segment id
    grade: Optional[str] = None
    fte: Optional[Decimal] = None               # e.g. 1.00, 0.50
    attributes: Optional[Dict[str, Any]] = None


class HRPositionOut(ORMBase):
    id: str
    title: str
    department_segment_id: Optional[str] = None
    grade: Optional[str] = None
    fte: Optional[Decimal] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
