# schemas/policysearchindex.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class PolicySearchIndexCreate(BaseModel):
    policy_id: str
    ts: Optional[str] = None


class PolicySearchIndexOut(ORMBase):
    policy_id: str
    ts: Optional[str] = None
