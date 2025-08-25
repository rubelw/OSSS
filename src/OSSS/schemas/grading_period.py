from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel

from .base import ORMBase


class GradingPeriodCreate(BaseModel):
    term_id: str
    name: str
    start_date: date
    end_date: date


class GradingPeriodOut(ORMBase):
    id: str
    term_id: str
    name: str
    start_date: date
    end_date: date
    created_at: datetime
    updated_at: datetime
