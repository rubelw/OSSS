# OSSS/schemas/message_recipient.py
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import Field
from OSSS.schemas.base import APIModel

class MessageRecipientBase(APIModel):
    message_id: str = Field(...)
    person_id: str = Field(...)
    delivery_status: Optional[str] = None
    delivered_at: Optional[datetime] = None

class MessageRecipientCreate(MessageRecipientBase):
    pass

class MessageRecipientReplace(MessageRecipientBase):
    pass

class MessageRecipientPatch(APIModel):
    message_id: Optional[str] = None
    person_id: Optional[str] = None
    delivery_status: Optional[str] = None
    delivered_at: Optional[datetime] = None

class MessageRecipientOut(MessageRecipientBase):
    id: str
    created_at: datetime
    updated_at: datetime

class MessageRecipientList(APIModel):
    items: List[MessageRecipientOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
