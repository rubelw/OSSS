# src/OSSS/schemas/agenda_item_approval.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from .base import ORMBase


class AgendaItemApprovalCreate(BaseModel):
    item_id: UUID
    step_id: UUID
    approver_id: Optional[UUID] = None
    decision: Optional[str] = None
    decided_at: Optional[datetime] = None
    comment: Optional[str] = None


class AgendaItemApprovalOut(ORMBase):
    id: UUID
    item_id: UUID
    step_id: UUID
    approver_id: Optional[UUID] = None
    decision: Optional[str] = None
    decided_at: Optional[datetime] = None
    comment: Optional[str] = None
