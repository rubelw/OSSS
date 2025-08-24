from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class LibraryItemOut(ORMBase):
    id: str
    school_id: str
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    barcode: Optional[str] = None
    created_at: datetime
    updated_at: datetime
