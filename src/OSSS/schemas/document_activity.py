from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel

from .base import ORMBase


class DocumentActivityCreate(BaseModel):
    document_id: str
    action: str
    actor_id: Optional[str] = None
    # If omitted, DB default (now()) will be used
    at: Optional[datetime] = None
    meta: Optional[Dict[str, Any]] = None


class DocumentActivityOut(ORMBase):
    id: str
    document_id: str
    action: str
    actor_id: Optional[str] = None
    at: datetime
    meta: Optional[Dict[str, Any]] = None
