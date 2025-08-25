# schemas/planassignment.py
from __future__ import annotations

from pydantic import BaseModel
from .base import ORMBase


class PlanAssignmentCreate(BaseModel):
    entity_type: str            # e.g., "plan" | "goal" | "objective"
    entity_id: str              # UUID as string
    assignee_type: str          # e.g., "user" | "group" | "role"
    assignee_id: str            # UUID as string


class PlanAssignmentOut(ORMBase):
    entity_type: str
    entity_id: str
    assignee_type: str
    assignee_id: str
