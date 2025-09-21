
from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel
from .common import OrderStatus

class TicketTypeBase(BaseModel):
    school_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    price_cents: int
    currency: str = "USD"
    quantity: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    class Config:
        from_attributes = True

class TicketTypeCreate(TicketTypeBase):
    id: Optional[str] = None

class TicketTypeRead(TicketTypeBase):
    id: str

class PassBase(BaseModel):
    school_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    price_cents: Optional[int] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    max_uses: Optional[int] = None
    class Config:
        from_attributes = True

class PassCreate(PassBase):
    id: Optional[str] = None

class PassRead(PassBase):
    id: str

class TicketOrderBase(BaseModel):
    school_id: str
    buyer_name: Optional[str] = None
    buyer_email: Optional[str] = None
    total_cents: int
    status: OrderStatus = "pending"
    class Config:
        from_attributes = True

class TicketOrderCreate(TicketOrderBase):
    id: Optional[str] = None

class TicketOrderRead(TicketOrderBase):
    id: str

class TicketBase(BaseModel):
    order_id: str
    ticket_type_id: str
    event_id: Optional[str] = None
    qr_code: Optional[str] = None
    status: OrderStatus = "paid"
    issued_at: Optional[datetime] = None
    redeemed_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class TicketCreate(TicketBase):
    id: Optional[str] = None

class TicketRead(TicketBase):
    id: str
