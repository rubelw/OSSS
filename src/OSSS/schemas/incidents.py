from __future__ import annotations
from typing import Optional
from datetime import datetime, date

from .base import ORMModel, TimestampMixin


class BehaviorCodeOut(ORMModel):
    code: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class IncidentOut(ORMModel, TimestampMixin):
    id: int
    school_id: Optional[str] = None
    occurred_at: datetime
    behavior_code: str
    description: Optional[str] = None


class IncidentParticipantOut(ORMModel, TimestampMixin):
    id: int
    incident_id: str
    person_id: str
    role: str


class ConsequenceTypeOut(ORMModel):
    code: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ConsequenceOut(ORMModel, TimestampMixin):
    id: int
    incident_id: str
    participant_id: str
    consequence_code: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None


class BehaviorInterventionOut(ORMModel, TimestampMixin):
    id: int
    student_id: str
    intervention: str
    start_date: date
    end_date: Optional[date] = None
