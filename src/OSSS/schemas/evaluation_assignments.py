# schemas/evaluationassignment.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class EvaluationAssignmentCreate(BaseModel):
    cycle_id: str
    subject_user_id: str
    evaluator_user_id: str
    template_id: str
    status: Optional[str] = None


class EvaluationAssignmentOut(ORMBase):
    id: str
    cycle_id: str
    subject_user_id: str
    evaluator_user_id: str
    template_id: str
    status: Optional[str] = None
    created_at: datetime
    updated_at: datetime
