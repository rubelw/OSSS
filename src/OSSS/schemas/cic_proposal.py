from __future__ import annotations
from typing import Optional
from datetime import datetime, date

from .base import ORMModel


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
