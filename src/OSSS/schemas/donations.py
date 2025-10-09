# src/OSSS/schemas/donations.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ---------- Base ----------

class DonationBase(BaseModel):
    campaign_id: str
    donor_name: Optional[str] = None
    donor_email: Optional[str] = None
    amount_cents: int
    method: Optional[str] = None  # e.g. cash, card, check, online
    donated_at: Optional[datetime] = None  # DB defaults to utcnow if not provided
    receipt_code: Optional[str] = None

    @field_validator("amount_cents")
    @classmethod
    def _non_negative_amount(cls, v: int) -> int:
        if v < 0:
            raise ValueError("amount_cents must be >= 0")
        return v


# ---------- Create / Update ----------

class DonationCreate(DonationBase):
    # same fields as base; donated_at is optional to let DB default kick in
    pass


class DonationUpdate(BaseModel):
    campaign_id: Optional[str] = None
    donor_name: Optional[str] = None
    donor_email: Optional[str] = None
    amount_cents: Optional[int] = None
    method: Optional[str] = None
    donated_at: Optional[datetime] = None
    receipt_code: Optional[str] = None

    @field_validator("amount_cents")
    @classmethod
    def _non_negative_amount(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("amount_cents must be >= 0")
        return v


# ---------- Read ----------

class DonationRead(DonationBase):
    id: str
    # donated_at will always be set on read (DB default), so make it non-optional here
    donated_at: datetime

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "DonationBase",
    "DonationCreate",
    "DonationUpdate",
    "DonationRead",
]
