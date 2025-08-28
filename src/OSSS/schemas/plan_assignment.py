# OSSS/schemas/plan_assignment.py
from __future__ import annotations
from typing import Optional, List
from pydantic import Field
from OSSS.schemas.base import APIModel

class PlanAssignmentBase(APIModel):
    entity_type: str = Field(..., max_length=50)
    entity_id: str = Field(...)
    assignee_type: str = Field(..., max_length=20)
    assignee_id: str = Field(...)

class PlanAssignmentCreate(PlanAssignmentBase): pass
class PlanAssignmentReplace(PlanAssignmentBase): pass

class PlanAssignmentPatch(APIModel):
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    assignee_type: Optional[str] = None
    assignee_id: Optional[str] = None

class PlanAssignmentOut(PlanAssignmentBase):
    id: str

class PlanAssignmentList(APIModel):
    items: List[PlanAssignmentOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
