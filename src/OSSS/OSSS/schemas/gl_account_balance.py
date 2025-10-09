from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from .base import ORMBase

class GlAccountBalanceBase(ORMBase):
    __abstract__ = True
    account_id: str
    fiscal_period_id: str
    begin_balance: Decimal = Decimal("0")
    debit_total: Decimal = Decimal("0")
    credit_total: Decimal = Decimal("0")
    end_balance: Decimal = Decimal("0")
    attributes: Optional[Dict[str, Any]] = None

class GlAccountBalanceCreate(GlAccountBalanceBase):
    pass

class GlAccountBalanceUpdate(ORMBase):
    begin_balance: Optional[Decimal] = None
    debit_total: Optional[Decimal] = None
    credit_total: Optional[Decimal] = None
    end_balance: Optional[Decimal] = None
    attributes: Optional[Dict[str, Any]] = None

class GlAccountBalanceOut(GlAccountBalanceBase):
    id: str
    created_at: datetime
    updated_at: datetime
