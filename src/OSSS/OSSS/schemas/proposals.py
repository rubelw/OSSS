from __future__ import annotations

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
import uuid

from pydantic import BaseModel, Field, ConfigDict


class ProposalStatusEnum(str, Enum):
    draft = "draft"
    submitted = "submitted"
    in_review = "in_review"
    approved = "approved"
    rejected = "rejected"


class ProposalBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        populate_by_name=True,
    )

    # GUID in DB → UUID here (Pydantic will parse from string)
    organization_id: Optional[uuid.UUID] = None
    association_id: Optional[uuid.UUID] = None

    # required: maps to committees.id (nullable=False in SQLA)
    committee_id: uuid.UUID = Field(..., description="FK to committees.id (required)")

    # optional FKs
    submitted_by_id: Optional[uuid.UUID] = Field(None, description="FK to persons.id")
    school_id: Optional[uuid.UUID] = Field(None, description="FK to schools.id")
    subject_id: Optional[uuid.UUID] = Field(None, description="FK to subjects.id")
    course_id: Optional[uuid.UUID] = Field(None, description="FK to courses.id")
    curriculum_id: Optional[uuid.UUID] = Field(None, description="FK to curricula.id")

    # core fields
    title: str = Field(..., max_length=255)
    summary: Optional[str] = None
    rationale: Optional[str] = None

    status: ProposalStatusEnum = Field(
        ProposalStatusEnum.draft,
        description="One of: draft, submitted, in_review, approved, rejected",
    )
    submitted_at: Optional[datetime] = None
    attributes: Optional[Dict[str, Any]] = None


class ProposalCreate(ProposalBase):
    # Inherits; committee_id required, others optional
    pass


class ProposalUpdate(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        populate_by_name=True,
    )

    organization_id: Optional[uuid.UUID] = None
    association_id: Optional[uuid.UUID] = None
    committee_id: Optional[uuid.UUID] = None
    submitted_by_id: Optional[uuid.UUID] = None
    school_id: Optional[uuid.UUID] = None
    subject_id: Optional[uuid.UUID] = None
    course_id: Optional[uuid.UUID] = None
    curriculum_id: Optional[uuid.UUID] = None

    title: Optional[str] = Field(None, max_length=255)
    summary: Optional[str] = None
    rationale: Optional[str] = None

    status: Optional[ProposalStatusEnum] = None
    submitted_at: Optional[datetime] = None
    attributes: Optional[Dict[str, Any]] = None


class ProposalRead(ProposalBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
