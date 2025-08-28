# OSSS/schemas/subscription.py
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from pydantic import Field
from OSSS.schemas.base import APIModel

class SubscriptionBase(APIModel):
    channel_id: str = Field(...)
    principal_type: str = Field(..., max_length=20)  # "user" | "group" | "role"
    principal_id: str = Field(...)

class SubscriptionCreate(SubscriptionBase): pass
class SubscriptionReplace(SubscriptionBase): pass

class SubscriptionPatch(APIModel):
    channel_id: Optional[str] = None
    principal_type: Optional[str] = None
    principal_id: Optional[str] = None

class SubscriptionOut(SubscriptionBase):
    id: str
    created_at: datetime

class SubscriptionList(APIModel):
    items: List[SubscriptionOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
