# schemas/consequence_types.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .base import ORMBase


class ConsequenceTypeCreate(BaseModel):
    code: str
    description: Optional[str] = None


class ConsequenceTypeOut(ORMBase):
    code: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
