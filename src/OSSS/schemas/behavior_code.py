from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class BehaviorCodeCreate(BaseModel):
    code: str
    description: Optional[str] = None


class BehaviorCodeOut(ORMBase):
    code: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
