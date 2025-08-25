# schemas/vote.py
from __future__ import annotations

from pydantic import BaseModel
from .base import ORMBase


class VoteCreate(BaseModel):
    motion_id: str
    voter_id: str
    value: str  # e.g., "yes" | "no" | "abstain"


class VoteOut(ORMBase):
    id: str
    motion_id: str
    voter_id: str
    value: str
