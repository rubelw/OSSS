from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class ExternalIdOut(ORMBase):
    id: str
    entity_type: str
    entity_id: str
    system: str
    external_id: str
    created_at: datetime
    updated_at: datetime
