from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class TestAdministrationOut(ORMBase):
    id: str
    test_id: str
    administration_date: date
    school_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
