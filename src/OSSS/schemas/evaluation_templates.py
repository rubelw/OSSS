# schemas/evaluation_templates.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class EvaluationTemplateCreate(BaseModel):
    name: str
    for_role: Optional[str] = None
    version: Optional[int] = 1
    is_active: Optional[bool] = True


class EvaluationTemplateOut(ORMBase):
    id: str
    name: str
    for_role: Optional[str] = None
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
