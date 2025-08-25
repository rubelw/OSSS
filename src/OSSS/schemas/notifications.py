from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel

from .base import ORMBase


class NotificationCreate(BaseModel):
    user_id: str
    type: str
    payload: Optional[Dict[str, Any]] = None
    read_at: Optional[datetime] = None


class NotificationOut(ORMBase):
    id: str
    user_id: str
    type: str
    payload: Optional[Dict[str, Any]] = None
    read_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
