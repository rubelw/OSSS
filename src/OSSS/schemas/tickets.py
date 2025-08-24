# src/OSSS/schemas/tickets.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import Field
from .base import ORMBase


TicketStatus = Literal["issued", "checked_in", "void"]


class TicketBase(ORMBase):
    order_id: str
    ticket_type_id: str
    serial_no: int = Field(..., ge=1)
    price_cents: int = Field(0, ge=0)
    holder_person_id: Optional[str] = None
    qr_code: Optional[str] = Field(None, max_length=128)
    status: TicketStatus = "issued"


class TicketCreate(TicketBase):
    """Payload for creating a new ticket."""
    # issued_at is set by the DB; clients usually omit it
    pass


# Alias if your routers expect `TicketIn`
TicketIn = TicketCreate


class TicketUpdate(ORMBase):
    """Partial update; all fields optional."""
    serial_no: Optional[int] = Field(None, ge=1)
    price_cents: Optional[int] = Field(None, ge=0)
    holder_person_id: Optional[str] = None
    qr_code: Optional[str] = Field(None, max_length=128)
    status: Optional[TicketStatus] = None
    checked_in_at: Optional[datetime] = None


class TicketOut(TicketBase):
    id: str
    issued_at: datetime
    checked_in_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
