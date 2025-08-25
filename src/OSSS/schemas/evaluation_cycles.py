# schemas/evaluationcycle.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class EvaluationCycleCreate(BaseModel):
    org_id: str
    name: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None


class EvaluationCycleOut(ORMBase):
    id: str
    org_id: str
    name: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
