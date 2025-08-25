from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel

from .base import ORMBase


class IncidentParticipantCreate(BaseModel):
    incident_id: str
    person_id: str
    role: str


class IncidentParticipantOut(ORMBase):
    id: str
    incident_id: str
    person_id: str
    role: str
    created_at: datetime
    updated_at: datetime
