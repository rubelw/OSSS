from __future__ import annotations
from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel

from .base import ORMModel


class CICMembershipCreate(BaseModel):
    committee_id: str
    person_id: str
    role: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    voting_member: bool = True


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
