from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel
from .base import ORMBase


class SisImportJobCreate(BaseModel):
    source: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    counts: Optional[Dict[str, Any]] = None
    error_log: Optional[str] = None


class SisImportJobOut(ORMBase):
    id: str
    source: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    counts: Optional[Dict[str, Any]] = None
    error_log: Optional[str] = None
    created_at: datetime
    updated_at: datetime
