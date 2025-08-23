from __future__ import annotations
from typing import Optional
from datetime import datetime, date

from .base import ORMModel


class CICCommitteeOut(ORMModel):
    id: str
    district_id: Optional[str] = None
    school_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class CICMembershipOut(ORMModel):
    id: str
    committee_id: str
    person_id: str
    role: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    voting_member: bool
    created_at: datetime
    updated_at: datetime


class CICMeetingOut(ORMModel):
    id: str
    committee_id: str
    title: str
    scheduled_at: datetime
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    status: str
    is_public: bool
    created_at: datetime
    updated_at: datetime


class CICAgendaItemOut(ORMModel):
    id: str
    meeting_id: str
    parent_id: Optional[str] = None
    position: int
    title: str
    description: Optional[str] = None
    time_allocated_minutes: Optional[int] = None
    subject_id: Optional[str] = None
    course_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CICMotionOut(ORMModel):
    id: str
    agenda_item_id: str
    text: str
    moved_by_id: Optional[str] = None
    seconded_by_id: Optional[str] = None
    result: Optional[str] = None
    tally_for: Optional[int] = None
    tally_against: Optional[int] = None
    tally_abstain: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class CICVoteOut(ORMModel):
    id: str
    motion_id: str
    person_id: str
    value: str
    created_at: datetime
    updated_at: datetime


class CICResolutionOut(ORMModel):
    id: str
    meeting_id: str
    title: str
    summary: Optional[str] = None
    effective_date: Optional[date] = None
    status: Optional[str] = None
    created_at: datetime
    updated_at: datetime


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
