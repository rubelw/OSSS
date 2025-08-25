# schemas/evaluationquestion.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .base import ORMBase


class EvaluationQuestionCreate(BaseModel):
    section_id: str
    text: str
    type: str  # scale | text | multi
    scale_min: Optional[int] = None
    scale_max: Optional[int] = None
    weight: Optional[float] = None


class EvaluationQuestionOut(ORMBase):
    id: str
    section_id: str
    text: str
    type: str
    scale_min: Optional[int] = None
    scale_max: Optional[int] = None
    weight: Optional[float] = None
    created_at: datetime
    updated_at: datetime
