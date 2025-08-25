# src/OSSS/schemas/agenda_workflow_step.py
from __future__ import annotations

from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from .base import ORMBase


class AgendaWorkflowStepCreate(BaseModel):
    workflow_id: UUID
    step_no: Optional[int] = 0
    approver_type: str
    approver_id: Optional[UUID] = None
    rule: Optional[str] = None


class AgendaWorkflowStepOut(ORMBase):
    id: UUID
    workflow_id: UUID
    step_no: int
    approver_type: str
    approver_id: Optional[UUID] = None
    rule: Optional[str] = None
