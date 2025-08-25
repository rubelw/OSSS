# schemas/evaluationsection.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .base import ORMBase


class EvaluationSectionCreate(BaseModel):
    template_id: str
    title: str
    order_no: Optional[int] = 0


class EvaluationSectionOut(ORMBase):
    id: str
    template_id: str
    title: str
    order_no: int
    created_at: datetime
    updated_at: datetime
