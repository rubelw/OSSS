# schemas/evaluationreport.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel

from .base import ORMBase


class EvaluationReportCreate(BaseModel):
    cycle_id: str
    scope: Optional[Dict[str, Any]] = None
    generated_at: datetime
    file_id: Optional[str] = None


class EvaluationReportOut(ORMBase):
    id: str
    cycle_id: str
    scope: Optional[Dict[str, Any]] = None
    generated_at: datetime
    file_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
