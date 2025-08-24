from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class AuditLogOut(ORMBase):
    id: str
    actor_id: Optional[str] = None
    action: str
    entity_type: str
    entity_id: str
    metadata_: Optional[Dict[str, Any]] = None
    occurred_at: datetime
