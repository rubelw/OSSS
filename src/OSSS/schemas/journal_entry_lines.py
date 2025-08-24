from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from .base import ORMBase

class JournalEntryLineBase(ORMBase):
    journal_entry_id: str
    line_no: int
    account_id: str
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    memo: Optional[str] = None
    segments_override: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None

class JournalEntryLineCreate(JournalEntryLineBase):
    pass

class JournalEntryLineUpdate(ORMBase):
    line_no: Optional[int] = None
    account_id: Optional[str] = None
    debit: Optional[Decimal] = None
    credit: Optional[Decimal] = None
    memo: Optional[str] = None
    segments_override: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None

class JournalEntryLineOut(JournalEntryLineBase):
    id: str
    created_at: datetime
    updated_at: datetime
