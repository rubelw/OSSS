from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class DocumentNotificationCreate(BaseModel):
    document_id: str
    user_id: str
    subscribed: Optional[bool] = True


class DocumentNotificationOut(ORMBase):
    document_id: str
    user_id: str
    subscribed: bool
    last_sent_at: Optional[datetime] = None
