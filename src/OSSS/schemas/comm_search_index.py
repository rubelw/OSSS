# schemas/commsearchindex.py
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class CommSearchIndexCreate(BaseModel):
    entity_type: str
    entity_id: str  # UUID as string


class CommSearchIndexOut(ORMBase):
    entity_type: str
    entity_id: str  # UUID as string
    ts: Optional[str] = None  # tsvector, exposed as text
