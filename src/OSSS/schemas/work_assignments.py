"""
Pydantic schemas for WorkAssignment

Follows the same style/pattern as other schemas in `src/OSSS/schemas`.
Backed by model defined in `db/models/work_assignments.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

# Keep enum aligned with the SQLAlchemy model if available
try:
    from OSSS.db.models.common_enums import WorkStatus  # type: ignore
except Exception:  # lightweight fallback for typing/runtime in isolation
    from enum import Enum

    class WorkStatus(str, Enum):  # type: ignore[no-redef]
        pending = "pending"
        in_progress = "in_progress"
        blocked = "blocked"
        completed = "completed"
        canceled = "canceled"


# ---- Base ----
class WorkAssignmentBase(BaseModel):
    """Shared fields between create/read/update for a WorkAssignment record."""

    title: str = Field(..., max_length=200, description="Short description of the work item.")
    details: Optional[str] = Field(
        default=None, description="Longer free-text notes/details for the task."
    )
    role: Optional[str] = Field(
        default=None, max_length=64, description="Role needed (e.g., 'stats', 'gate', 'announcer')."
    )
    status: WorkStatus = Field(
        default=WorkStatus.pending, description="Lifecycle state of this assignment."
    )
    due_at: Optional[datetime] = Field(
        default=None, description="When the assignment is due (UTC)."
    )
    started_at: Optional[datetime] = Field(
        default=None, description="When work started (UTC)."
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="When work completed (UTC)."
    )


# ---- Create ----
class WorkAssignmentCreate(WorkAssignmentBase):
    """Payload for creating a new WorkAssignment."""

    # relationships
    team_id: UUID = Field(description="FK to the associated team.")
    assignee_id: Optional[UUID] = Field(
        default=None, description="FK to the assigned user (nullable)."
    )
    event_id: Optional[UUID] = Field(
        default=None, description="FK to an event this work is tied to (nullable)."
    )


# ---- Update (PATCH) ----
class WorkAssignmentUpdate(BaseModel):
    """Partial update for an existing WorkAssignment."""

    title: Optional[str] = Field(default=None, max_length=200)
    details: Optional[str] = None
    role: Optional[str] = Field(default=None, max_length=64)
    status: Optional[WorkStatus] = None
    due_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    team_id: Optional[UUID] = None
    assignee_id: Optional[UUID] = None
    event_id: Optional[UUID] = None


# ---- Read ----
class WorkAssignmentRead(WorkAssignmentBase):
    """Replica of a persisted WorkAssignment (as returned by the API)."""

    id: UUID
    team_id: UUID
    assignee_id: Optional[UUID] = None
    event_id: Optional[UUID] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Pydantic v2: allow construction from ORM objects
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


# ---- Lightweight summaries / lists ----
class WorkAssignmentSummary(BaseModel):
    """Minimal listing view of assignments for tables or dropdowns."""

    id: UUID
    team_id: UUID
    assignee_id: Optional[UUID] = None
    event_id: Optional[UUID] = None
    title: str
    status: WorkStatus
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkAssignmentList(BaseModel):
    """Container useful for list endpoints that wrap results (kept optional)."""

    items: list[WorkAssignmentSummary]
    total: int = Field(description="Total matching records (for pagination).")
