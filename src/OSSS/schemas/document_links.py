from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel

from .base import ORMBase


class DocumentLinkCreate(BaseModel):
    document_id: str
    entity_type: str
    entity_id: str


class DocumentLinkOut(ORMBase):
    id: str
    document_id: str
    entity_type: str
    entity_id: str
    created_at: datetime
    updated_at: datetime
