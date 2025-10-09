# src/OSSS/schemas/order_create.py
from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field, model_validator

from .line_item import LineItem


class OrderCreate(BaseModel):
    """Payload to create an order for an event."""
    event_id: str = Field(..., description="ID of the event the order is for")
    items: List[LineItem] = Field(
        ..., min_length=1, description="List of ticket-type line items"
    )

    @model_validator(mode="after")
    def _no_duplicate_ticket_types(self) -> "OrderCreate":
        """Prevent sending the same ticket_type_id multiple times."""
        seen: set[str] = set()
        dups: set[str] = set()
        for li in self.items:
            if li.ticket_type_id in seen:
                dups.add(li.ticket_type_id)
            seen.add(li.ticket_type_id)
        if dups:
            raise ValueError(
                f"Duplicate ticket_type_id not allowed: {', '.join(sorted(dups))}"
            )
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_id": "e7b73b1e-5d3c-4e5b-9d9a-2a1f0f4c9d11",
                "items": [
                    {
                        "ticket_type_id": "b0e6c2b9-6c9d-4f37-9c9a-5b6c9b1c23ab",
                        "quantity": 2
                    },
                    {
                        "ticket_type_id": "a1c2d3e4-f5a6-4b7c-8d9e-0f1a2b3c4d5e",
                        "quantity": 1
                    }
                ]
            }
        }
    }
