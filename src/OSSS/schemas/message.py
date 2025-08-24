from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class MessageOut(ORMBase):
    id: str
    sender_id: Optional[str] = None
    channel: str
    subject: Optional[str] = None
    body: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
