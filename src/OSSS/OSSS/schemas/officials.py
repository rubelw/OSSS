"""
Pydantic schemas for Official

Follows the same style/pattern as other schemas in `src/OSSS/schemas`.
Backed by model defined in `db/models/officials.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr


# ---- Base ----
class OfficialBase(BaseModel):
    """Shared fields between create/read/update for an Official record."""

    name: Optional[str] = Field(
        default=None, description="Official's full name (optional)."
    )
    certification: Optional[str] = Field(
        default=None, description="Certification or level (optional)."
    )
    phone: Optional[str] = Field(
        default=None, description="Contact phone number (optional)."
    )
    email: Optional[EmailStr] = Field(
        default=None, description="Contact email (optional)."
    )


# ---- Create ----
class OfficialCreate(OfficialBase):
    """Payload for creating a new Official."""

    # Relationship foreign key
    school_id: UUID = Field(description="FK to the associated school.")


# ---- Update (PATCH) ----
class OfficialUpdate(BaseModel):
    """Partial update for an existing Official."""

    name: Optional[str] = None
    certification: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    school_id: Optional[UUID] = None


# ---- Read ----
class OfficialRead(OfficialBase):
    """Replica of a persisted Official (as returned by the API)."""

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
class OfficialSummary(BaseModel):
    """Minimal listing view of officials for tables or dropdowns."""

    id: UUID
    school_id: UUID
    name: Optional[str] = None
    certification: Optional[str] = None

    model_config = {"from_attributes": True}


class OfficialList(BaseModel):
    """Container useful for list endpoints that wrap results (kept optional)."""

    items: list[OfficialSummary]
    total: int = Field(description="Total matching records (for pagination).")
