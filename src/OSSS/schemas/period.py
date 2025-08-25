from __future__ import annotations

from datetime import time, datetime
from typing import Optional

from .base import ORMBase
from pydantic import BaseModel


class PeriodCreate(BaseModel):
    bell_schedule_id: str
    name: str
    start_time: time
    end_time: time
    sequence: Optional[int] = None


class PeriodOut(ORMBase):
    id: str
    bell_schedule_id: str
    name: str
    start_time: time
    end_time: time
    sequence: Optional[int] = None
    created_at: datetime
    updated_at: datetime
