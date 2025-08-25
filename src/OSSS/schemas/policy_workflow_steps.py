# schemas/policyworkflowstep.py
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class PolicyWorkflowStepCreate(BaseModel):
    workflow_id: str
    step_no: int
    approver_type: str          # "user" | "group" | "role"
    approver_id: Optional[str] = None
    rule: Optional[str] = None


class PolicyWorkflowStepOut(ORMBase):
    id: str
    workflow_id: str
    step_no: int
    approver_type: str
    approver_id: Optional[str] = None
    rule: Optional[str] = None
