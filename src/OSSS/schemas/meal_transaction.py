from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class MealTransactionOut(ORMBase):
    id: str
    account_id: str
    transacted_at: datetime
    amount: Decimal
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
