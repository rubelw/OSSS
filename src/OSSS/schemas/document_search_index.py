from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class DocumentSearchIndexCreate(BaseModel):
    document_id: str
    # Usually filled by DB trigger / computed search vector; allow optional on create
    ts: Optional[str] = None


class DocumentSearchIndexOut(ORMBase):
    document_id: str
    ts: Optional[str] = None
