from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

# Shared config to allow ORM -> Pydantic
class Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# -------- Activity --------
class ActivityIn(BaseModel):
    school_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    is_active: Optional[bool] = True

class ActivityOut(Orm):
    id: str
    school_id: Optional[str]
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

# -------- Event --------
class EventIn(BaseModel):
    school_id: str
    activity_id: Optional[str] = None
    title: str
    summary: Optional[str] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None
    venue: Optional[str] = None
    status: Optional[str] = "draft"
    attributes: Optional[dict] = None

class EventOut(Orm):
    id: str
    school_id: str
    activity_id: Optional[str]
    title: str
    summary: Optional[str]
    starts_at: datetime
    ends_at: Optional[datetime]
    venue: Optional[str]
    status: str
    attributes: Optional[dict]
    created_at: datetime
    updated_at: datetime

# -------- TicketType --------
class TicketTypeIn(BaseModel):
    name: str
    price_cents: int = 0
    quantity_total: int = 0
    sales_starts_at: Optional[datetime] = None
    sales_ends_at: Optional[datetime] = None
    attributes: Optional[dict] = None

class TicketTypeOut(Orm):
    id: str
    event_id: str
    name: str
    price_cents: int
    quantity_total: int
    quantity_sold: int
    sales_starts_at: Optional[datetime]
    sales_ends_at: Optional[datetime]
    attributes: Optional[dict]
    created_at: datetime
    updated_at: datetime

# -------- Ordering --------
class LineItem(BaseModel):
    ticket_type_id: str
    quantity: int = Field(gt=0)

class OrderCreate(BaseModel):
    event_id: str
    items: List[LineItem]

class TicketOut(Orm):
    id: str
    order_id: str
    ticket_type_id: str
    serial_no: int
    price_cents: int
    status: str
    qr_code: Optional[str]
    issued_at: datetime
    checked_in_at: Optional[datetime]

class OrderOut(Orm):
    id: str
    event_id: str
    purchaser_user_id: Optional[str]
    total_cents: int
    currency: str
    status: str
    external_ref: Optional[str]
    created_at: datetime
    updated_at: datetime
    tickets: list[TicketOut] = []

# -------- Scanning --------
class ScanRequest(BaseModel):
    qr_code: str
    location: Optional[str] = None

class ScanResult(BaseModel):
    ok: bool
    ticket_id: Optional[str] = None
    status: Optional[str] = None
    message: str
