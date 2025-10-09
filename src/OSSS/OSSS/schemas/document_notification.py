# OSSS/schemas/document_notification.py
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import Field
from OSSS.schemas.base import APIModel

class DocumentNotificationBase(APIModel):
    document_id: str = Field(...)
    user_id: str = Field(...)
    subscribed: Optional[bool] = None   # allow server_default true to apply
    last_sent_at: Optional[datetime] = None

class DocumentNotificationCreate(DocumentNotificationBase): pass
class DocumentNotificationReplace(DocumentNotificationBase): pass

class DocumentNotificationPatch(APIModel):
    subscribed: Optional[bool] = None
    last_sent_at: Optional[datetime] = None

class DocumentNotificationOut(DocumentNotificationBase):
    id: str

class DocumentNotificationList(APIModel):
    items: List[DocumentNotificationOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
