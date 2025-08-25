# schemas/subscription.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from .base import ORMBase


class SubscriptionCreate(BaseModel):
    channel_id: str
    principal_type: str   # "user" | "group" | "role"
    principal_id: str


class SubscriptionOut(ORMBase):
    channel_id: str
    principal_type: str
    principal_id: str
    created_at: datetime
