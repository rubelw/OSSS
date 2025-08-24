from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime, date
from .base import ORMBase

class FiscalYearBase(ORMBase):
    code: str
    start_date: date
    end_date: date
    is_closed: bool = False
    attributes: Optional[Dict[str, Any]] = None

class FiscalYearCreate(FiscalYearBase):
    pass

class FiscalYearUpdate(ORMBase):
    code: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_closed: Optional[bool] = None
    attributes: Optional[Dict[str, Any]] = None

class FiscalYearOut(FiscalYearBase):
    id: str
    created_at: datetime
    updated_at: datetime
