from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from .base import ORMBase

class ExportRunOut(ORMBase):
    id: str
    export_name: str
    ran_at: datetime
    status: str
    file_uri: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
