# schemas/paychecks.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import Field, field_validator

from .base import ORMBase  # ORMBase should enable from_attributes=True


class PaycheckBase(ORMBase):
    run_id: str
    employee_id: str
    check_no: Optional[str] = Field(None, max_length=32, description="Check/advice number")
    gross_pay: Decimal = Field(..., ge=Decimal("0"))
    net_pay: Decimal = Field(..., ge=Decimal("0"))
    taxes: Optional[dict[str, Any]] = None
    attributes: Optional[dict[str, Any]] = None

    @field_validator("check_no")
    @classmethod
    def _blank_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        return v or None


class PaycheckCreate(PaycheckBase):
    """Payload to create a paycheck."""
    pass


class PaycheckUpdate(ORMBase):
    """Partial update for a paycheck (all fields optional)."""
    run_id: Optional[str] = None
    employee_id: Optional[str] = None
    check_no: Optional[str] = Field(None, max_length=32)
    gross_pay: Optional[Decimal] = Field(None, ge=Decimal("0"))
    net_pay: Optional[Decimal] = Field(None, ge=Decimal("0"))
    taxes: Optional[dict[str, Any]] = None
    attributes: Optional[dict[str, Any]] = None

    @field_validator("check_no")
    @classmethod
    def _blank_to_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        return v or None


class PaycheckOut(ORMBase):
    id: str
    run_id: str
    employee_id: str
    check_no: Optional[str] = None
    gross_pay: Decimal
    net_pay: Decimal
    taxes: Optional[dict[str, Any]] = None
    attributes: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


__all__ = ["PaycheckCreate", "PaycheckUpdate", "PaycheckOut"]
