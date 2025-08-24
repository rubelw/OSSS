from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime, date
from .base import ORMBase

class FiscalPeriodBase(ORMBase):
    fiscal_year_id: str
    period_no: int    # 1..13
    name: str
    start_date: date
    end_date: date
    is_closed: bool = False
    attributes: Optional[Dict[str, Any]] = None

class FiscalPeriodCreate(FiscalPeriodBase):
    pass

class FiscalPeriodUpdate(ORMBase):
    fiscal_year_id: Optional[str] = None
    period_no: Optional[int] = None
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_closed: Optional[bool] = None
    attributes: Optional[Dict[str, Any]] = None

class FiscalPeriodOut(FiscalPeriodBase):
    id: str
    created_at: datetime
    updated_at: datetime
