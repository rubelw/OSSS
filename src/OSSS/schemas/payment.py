from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class PaymentOut(ORMBase):
    id: str
    invoice_id: str
    paid_on: date
    amount: Decimal
    method: Optional[str] = None
    created_at: datetime
    updated_at: datetime
