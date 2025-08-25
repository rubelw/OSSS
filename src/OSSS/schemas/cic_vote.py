from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel

from .base import ORMModel


class CICVoteCreate(BaseModel):
    motion_id: str
    person_id: str
    value: str  # e.g. "for" | "against" | "abstain"


class CICVoteOut(ORMModel):
    id: str
    motion_id: str
    person_id: str
    value: str
    created_at: datetime
    updated_at: datetime
