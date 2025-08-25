# src/OSSS/schemas/agenda_workflow.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from .base import ORMBase


class AgendaWorkflowCreate(BaseModel):
    name: str
    active: Optional[bool] = True


class AgendaWorkflowOut(ORMBase):
    id: UUID
    name: str
    active: bool

class AgendaWorkflowUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None
