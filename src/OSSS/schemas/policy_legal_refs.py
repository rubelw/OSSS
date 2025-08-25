# schemas/policylegalref.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class PolicyLegalRefCreate(BaseModel):
    policy_version_id: str
    citation: str
    url: Optional[str] = None


class PolicyLegalRefOut(ORMBase):
    id: str
    policy_version_id: str
    citation: str
    url: Optional[str] = None
