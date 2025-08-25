# schemas/policycomment.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class PolicyCommentCreate(BaseModel):
    policy_version_id: str
    user_id: Optional[str] = None
    text: str
    visibility: str = "public"


class PolicyCommentOut(ORMBase):
    id: str
    policy_version_id: str
    user_id: Optional[str] = None
    text: str
    visibility: str
    created_at: datetime
    updated_at: datetime
