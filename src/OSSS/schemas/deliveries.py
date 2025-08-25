from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class DeliveryCreate(BaseModel):
    post_id: str
    user_id: str
    delivered_at: Optional[datetime] = None
    # medium: email | push | rss (no enum to keep simple)
    medium: Optional[str] = None
    # status: sent | failed | opened
    status: Optional[str] = None


class DeliveryOut(ORMBase):
    id: str
    post_id: str
    user_id: str
    delivered_at: Optional[datetime] = None
    medium: Optional[str] = None
    status: Optional[str] = None
