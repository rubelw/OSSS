# src/OSSS/schemas/order_line_item.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from .base import ORMModel  # must provide model_config = {"from_attributes": True}


class OrderLineItemBase(BaseModel):
    ticket_type_id: str = Field(..., description="Ticket type being purchased")
    quantity: int = Field(..., gt=0, description="Number of tickets of this type")


class OrderLineItemCreate(OrderLineItemBase):
    order_id: str = Field(..., description="Owning order ID")

    model_config = {
        "json_schema_extra": {
            "example": {
                "order_id": "e3c1a0f4-2a3b-4a1b-8a1b-9f6c7d5e2a10",
                "ticket_type_id": "c9a8b7d6-5e4f-4321-9abc-0123456789ab",
                "quantity": 2,
            }
        }
    }


class OrderLineItemUpdate(BaseModel):
    quantity: Optional[int] = Field(None, gt=0, description="New quantity (must be > 0)")

    model_config = {
        "json_schema_extra": {"example": {"quantity": 3}}
    }


class OrderLineItemOut(ORMModel):
    id: str
    order_id: str
    ticket_type_id: str
    quantity: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "7d7a0b2a-9a8c-4b9c-8d6f-1c2b3a4d5e6f",
                "order_id": "e3c1a0f4-2a3b-4a1b-8a1b-9f6c7d5e2a10",
                "ticket_type_id": "c9a8b7d6-5e4f-4321-9abc-0123456789ab",
                "quantity": 2,
                "created_at": "2025-08-24T15:30:00Z",
                "updated_at": "2025-08-24T15:30:00Z",
            }
        },
    }
