from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel

from .base import ORMBase


class PMWorkGeneratorCreate(BaseModel):
    pm_plan_id: str
    last_generated_at: Optional[datetime] = None
    lookahead_days: Optional[int] = None
    attributes: Optional[Dict[str, Any]] = None


class PMWorkGeneratorOut(ORMBase):
    id: str
    pm_plan_id: str
    last_generated_at: Optional[datetime] = None
    lookahead_days: Optional[int] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
