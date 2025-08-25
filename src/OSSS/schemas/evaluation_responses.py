# schemas/evaluationresponse.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .base import ORMBase


class EvaluationResponseCreate(BaseModel):
    assignment_id: str
    question_id: str
    value_num: Optional[float] = None
    value_text: Optional[str] = None
    comment: Optional[str] = None
    answered_at: Optional[datetime] = None


class EvaluationResponseOut(ORMBase):
    id: str
    assignment_id: str
    question_id: str
    value_num: Optional[float] = None
    value_text: Optional[str] = None
    comment: Optional[str] = None
    answered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
