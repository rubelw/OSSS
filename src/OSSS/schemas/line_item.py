# src/OSSS/schemas/line_item.py
from __future__ import annotations

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    """One ticket-type entry in an order request."""
    ticket_type_id: str = Field(..., description="ID of the ticket type being purchased")
    quantity: int = Field(..., gt=0, description="Number of tickets of this type")

    model_config = {
        "json_schema_extra": {
            "example": {
                "ticket_type_id": "b0e6c2b9-6c9d-4f37-9c9a-5b6c9b1c23ab",
                "quantity": 2,
            }
        }
    }
