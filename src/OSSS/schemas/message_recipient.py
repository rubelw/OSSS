from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class MessageRecipientCreate(BaseModel):
    message_id: str
    person_id: str
    delivery_status: Optional[str] = None
    delivered_at: Optional[datetime] = None


class MessageRecipientOut(ORMBase):
    message_id: str
    person_id: str
    delivery_status: Optional[str] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
