"""
Pydantic schemas for Worker

Follows the same style/pattern as other schemas in `src/OSSS/schemas`.
Backed by model defined in `db/models/workers.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr


# ---- Base ----
class WorkerBase(BaseModel):
    """Shared fields between create/read/update for a Worker record."""

    name: Optional[str] = Field(default=None, max_length=128, description="Worker's display name.")
    role: Optional[str] = Field(
        default=None, max_length=128, description="Role like 'gate', 'clock', 'chain crew'."
    )
    phone: Optional[str] = Field(default=None, max_length=64, description="Contact phone (optional).")
    email: Optional[EmailStr] = Field(default=None, description="Contact email (optional).")


# ---- Create ----
class WorkerCreate(WorkerBase):
    """Payload for creating a new Worker."""

    school_id: UUID = Field(description="FK to the associated school.")


# ---- Update (PATCH) ----
class WorkerUpdate(BaseModel):
    """Partial update for an existing Worker."""

    name: Optional[str] = Field(default=None, max_length=128)
    role: Optional[str] = Field(default=None, max_length=128)
    phone: Optional[str] = Field(default=None, max_length=64)
    email: Optional[EmailStr] = None
    school_id: Optional[UUID] = None


# ---- Read ----
class WorkerRead(WorkerBase):
    """Replica of a persisted Worker (as returned by the API)."""

    id: UUID
    school_id: UUID

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Pydantic v2: allow construction from ORM objects
    model_config = {
        "from_attributes": True,
        "populate_by_name": True,
    }


# ---- Lightweight summaries / lists ----
class WorkerSummary(BaseModel):
    """Minimal listing view of workers for tables or dropdowns."""

    id: UUID
    school_id: UUID
    name: Optional[str] = None
    role: Optional[str] = None

    model_config = {"from_attributes": True}


class WorkerList(BaseModel):
    """Container useful for list endpoints that wrap results (kept optional)."""

    items: list[WorkerSummary]
    total: int = Field(description="Total matching records (for pagination).")
