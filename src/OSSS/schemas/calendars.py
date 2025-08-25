from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel

from .base import ORMModel


class CalendarCreate(BaseModel):
    school_id: str
    name: str


class CalendarOut(ORMModel):
    id: str
    school_id: str
    name: str
    created_at: datetime
    updated_at: datetime
