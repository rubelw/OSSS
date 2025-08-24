from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class UserAccountOut(ORMBase):
    id: str
    person_id: str
    username: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
