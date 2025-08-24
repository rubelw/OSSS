# src/OSSS/schemas/ticket_types.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from .base import ORMModel  # Pydantic model with from_attributes=True


class TicketTypeBase(BaseModel):
    event_id: str
    name: str
    price_cents: int = 0
    quantity_total: int = 0
    sales_starts_at: Optional[datetime] = None
    sales_ends_at: Optional[datetime] = None
    attributes: Optional[dict] = None

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def _validate(self):
        if self.price_cents is not None and self.price_cents < 0:
            raise ValueError("price_cents must be >= 0")
        if self.quantity_total is not None and self.quantity_total < 0:
            raise ValueError("quantity_total must be >= 0")
        if (
            self.sales_starts_at is not None
            and self.sales_ends_at is not None
            and self.sales_ends_at < self.sales_starts_at
        ):
            raise ValueError("sales_ends_at must be >= sales_starts_at")
        return self


class TicketTypeCreate(TicketTypeBase):
    """Payload for creating a ticket type."""
    pass


# Back-compat alias if routers import EventIn-style names
TicketTypeIn = TicketTypeCreate


class TicketTypeUpdate(BaseModel):
    """Partial update for a ticket type (all fields optional)."""
    event_id: Optional[str] = None
    name: Optional[str] = None
    price_cents: Optional[int] = None
    quantity_total: Optional[int] = None
    sales_starts_at: Optional[datetime] = None
    sales_ends_at: Optional[datetime] = None
    attributes: Optional[dict] = None

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def _validate(self):
        if self.price_cents is not None and self.price_cents < 0:
            raise ValueError("price_cents must be >= 0")
        if self.quantity_total is not None and self.quantity_total < 0:
            raise ValueError("quantity_total must be >= 0")
        if (
            self.sales_starts_at is not None
            and self.sales_ends_at is not None
            and self.sales_ends_at < self.sales_starts_at
        ):
            raise ValueError("sales_ends_at must be >= sales_starts_at")
        return self


class TicketTypeOut(ORMModel):
    id: str
    event_id: str
    name: str
    price_cents: int
    quantity_total: int
    quantity_sold: int
    sales_starts_at: Optional[datetime] = None
    sales_ends_at: Optional[datetime] = None
    attributes: Optional[dict] = None

    created_at: datetime
    updated_at: datetime


__all__ = [
    "TicketTypeBase",
    "TicketTypeCreate",
    "TicketTypeIn",
    "TicketTypeUpdate",
    "TicketTypeOut",
]
