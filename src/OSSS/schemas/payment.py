from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from .base import ORMBase
from pydantic import BaseModel


class PaymentCreate(BaseModel):
    invoice_id: str
    paid_on: date
    amount: Decimal
    method: Optional[str] = None


class PaymentOut(ORMBase):
    id: str
    invoice_id: str
    paid_on: date
    amount: Decimal
    method: Optional[str] = None
    created_at: datetime
    updated_at: datetime
