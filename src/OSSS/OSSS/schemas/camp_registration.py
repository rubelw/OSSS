# src/OSSS/schemas/camp_registration.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

# Prefer importing the enum from the model so we keep one source of truth.
# If your enum lives elsewhere, adjust this import accordingly.
try:
    from OSSS.db.models.camp_registrations import OrderStatus  # type: ignore
except Exception:  # pragma: no cover - fallback for local IDEs without full env
    from enum import Enum

    class OrderStatus(str, Enum):
        pending = "pending"
        paid = "paid"
        cancelled = "cancelled"
        refunded = "refunded"


__all__ = [
    "CampRegistrationBase",
    "CampRegistrationCreate",
    "CampRegistrationUpdate",
    "CampRegistrationRead",
]


class CampRegistrationBase(BaseModel):
    """Fields shared by create/read/update (minus id/timestamps)."""

    camp_id: int = Field(..., description="FK to camps.id")
    participant_name: Optional[str] = Field(None, max_length=255)
    participant_grade: Optional[str] = Field(None, max_length=64)
    guardian_contact: Optional[str] = Field(None, max_length=255)
    paid_amount_cents: Optional[int] = Field(None, ge=0)
    # Let the API default to OrderStatus.pending if not provided
    status: Optional[OrderStatus] = None
    # DB has a default; accept/echo it in read, allow override in create if desired
    registered_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CampRegistrationCreate(CampRegistrationBase):
    """Payload for POST /camp-registrations."""
    # All requirements already captured in Base; keep as-is.
    pass


class CampRegistrationUpdate(BaseModel):
    """Partial update; all fields optional."""

    camp_id: Optional[int] = None
    participant_name: Optional[str] = Field(None, max_length=255)
    participant_grade: Optional[str] = Field(None, max_length=64)
    guardian_contact: Optional[str] = Field(None, max_length=255)
    paid_amount_cents: Optional[int] = Field(None, ge=0)
    status: Optional[OrderStatus] = None
    registered_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CampRegistrationRead(CampRegistrationBase):
    """Representation returned from the API."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
