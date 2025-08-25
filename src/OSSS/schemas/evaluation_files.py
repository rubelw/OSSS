# schemas/evaluationfile.py
from __future__ import annotations

from pydantic import BaseModel

from .base import ORMBase


class EvaluationFileCreate(BaseModel):
    assignment_id: str
    file_id: str


class EvaluationFileOut(ORMBase):
    assignment_id: str
    file_id: str
