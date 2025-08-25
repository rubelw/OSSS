from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import BaseModel, Field

from .base import ORMBase


class AuditLogCreate(BaseModel):
    actor_id: Optional[str] = None
    action: str = Field(..., min_length=1)
    entity_type: str = Field(..., min_length=1)
    entity_id: str = Field(..., min_length=1)
    metadata_: Optional[Dict[str, Any]] = None
    # Let the server/DB default this if omitted
    occurred_at: Optional[datetime] = None


class AuditLogOut(ORMBase):
    id: str
    actor_id: Optional[str] = None
    action: str
    entity_type: str
    entity_id: str
    metadata_: Optional[Dict[str, Any]] = None
    occurred_at: datetime
