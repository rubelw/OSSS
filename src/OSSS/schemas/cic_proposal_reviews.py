from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel

from .base import ORMModel

Decision = Literal["approve", "reject", "revise"]


class CICProposalReviewCreate(BaseModel):
    proposal_id: str
    reviewer_id: Optional[str] = None
    decision: Optional[Decision] = None
    decided_at: Optional[datetime] = None
    comment: Optional[str] = None


class CICProposalReviewOut(ORMModel):
    id: str
    proposal_id: str
    reviewer_id: Optional[str] = None
    decision: Optional[Decision] = None
    decided_at: Optional[datetime] = None
    comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime
