from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class MealTransactionCreate(BaseModel):
    account_id: str
    amount: Decimal
    transacted_at: Optional[datetime] = None
    description: Optional[str] = None


class MealTransactionOut(ORMBase):
    id: str
    account_id: str
    transacted_at: datetime
    amount: Decimal
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
