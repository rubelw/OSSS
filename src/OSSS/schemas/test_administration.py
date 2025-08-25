from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class TestAdministrationCreate(BaseModel):
    test_id: str
    administration_date: date
    school_id: Optional[str] = None


class TestAdministrationOut(ORMBase):
    id: str
    test_id: str
    administration_date: date
    school_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
