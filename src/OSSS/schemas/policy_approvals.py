# schemas/policyapproval.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class PolicyApprovalCreate(BaseModel):
    policy_version_id: str
    step_id: str
    approver_id: Optional[str] = None
    decision: Optional[str] = None
    decided_at: Optional[datetime] = None  # timezone-aware if provided
    comment: Optional[str] = None


class PolicyApprovalOut(ORMBase):
    id: str
    policy_version_id: str
    step_id: str
    approver_id: Optional[str] = None
    decision: Optional[str] = None
    decided_at: Optional[datetime] = None
    comment: Optional[str] = None
