# schemas/policypublication.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class PolicyPublicationCreate(BaseModel):
    policy_version_id: str
    published_at: Optional[datetime] = None  # defaults to DB now() if not provided
    public_url: Optional[str] = None
    is_current: bool = False


class PolicyPublicationOut(ORMBase):
    policy_version_id: str
    published_at: datetime
    public_url: Optional[str] = None
    is_current: bool
