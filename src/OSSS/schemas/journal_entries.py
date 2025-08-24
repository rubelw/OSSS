from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime, date
from .base import ORMBase

class JournalEntryBase(ORMBase):
    fiscal_year_id: Optional[str] = None
    fiscal_period_id: Optional[str] = None
    entry_date: date
    batch_no: Optional[str] = None
    source: Optional[str] = None       # GL/AP/AR/PR/JE
    reference: Optional[str] = None
    description: Optional[str] = None
    status: str = "open"               # open/posted/void
    posted_at: Optional[datetime] = None
    posted_by_user_id: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None

class JournalEntryCreate(JournalEntryBase):
    pass

class JournalEntryUpdate(ORMBase):
    fiscal_year_id: Optional[str] = None
    fiscal_period_id: Optional[str] = None
    entry_date: Optional[date] = None
    batch_no: Optional[str] = None
    source: Optional[str] = None
    reference: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    posted_at: Optional[datetime] = None
    posted_by_user_id: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None

class JournalEntryOut(JournalEntryBase):
    id: str
    created_at: datetime
    updated_at: datetime
