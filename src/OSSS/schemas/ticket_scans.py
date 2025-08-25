# schemas/ticketscan.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel
from .base import ORMBase


class TicketScanCreate(BaseModel):
    ticket_id: str
    result: str                      # "ok" | "duplicate" | "invalid" | "void"
    scanned_by_user_id: Optional[str] = None
    scanned_at: Optional[datetime] = None  # defaults to DB now() if omitted
    location: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class TicketScanOut(ORMBase):
    id: str
    ticket_id: str
    result: str
    scanned_by_user_id: Optional[str] = None
    scanned_at: datetime
    location: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
