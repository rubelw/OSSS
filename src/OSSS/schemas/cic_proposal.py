from __future__ import annotations
from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel

from .base import ORMModel


class CICProposalCreate(BaseModel):
    committee_id: str
    type: str
    title: str
    status: str  # e.g. "draft", "submitted", etc.
    submitted_by_id: Optional[str] = None
    school_id: Optional[str] = None
    subject_id: Optional[str] = None
    course_id: Optional[str] = None
    rationale: Optional[str] = None
    submitted_at: Optional[datetime] = None
    review_deadline: Optional[date] = None


class CICProposalOut(ORMModel):
    id: str
    committee_id: str
    submitted_by_id: Optional[str] = None
    school_id: Optional[str] = None
    type: str
    subject_id: Optional[str] = None
    course_id: Optional[str] = None
    title: str
    rationale: Optional[str] = None
    status: str
    submitted_at: datetime
    review_deadline: Optional[date] = None
    created_at: datetime
    updated_at: datetime
