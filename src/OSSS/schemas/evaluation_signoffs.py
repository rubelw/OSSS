# schemas/evaluationsignoff.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .base import ORMBase


class EvaluationSignoffCreate(BaseModel):
    assignment_id: str
    signer_id: str
    signed_at: datetime
    note: Optional[str] = None


class EvaluationSignoffOut(ORMBase):
    id: str
    assignment_id: str
    signer_id: str
    signed_at: datetime
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime
