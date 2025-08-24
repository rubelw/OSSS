# schemas/pay_periods.py
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import Field, field_validator, model_validator

from .base import ORMBase  # assumes you have ORMBase with model_config = from_attributes=True


Status = Literal["open", "locked", "posted"]


class PayPeriodBase(ORMBase):
    code: str = Field(..., max_length=32)
    start_date: date
    end_date: date
    pay_date: date
    status: Status = "open"

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("code cannot be empty")
        return v

    @model_validator(mode="after")
    def _check_dates(self) -> "PayPeriodBase":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.pay_date < self.start_date:
            raise ValueError("pay_date must be on or after start_date")
        return self


class PayPeriodCreate(PayPeriodBase):
    """
    All required except status (defaults to 'open').
    """
    pass


class PayPeriodUpdate(ORMBase):
    """
    All fields optional; only provided fields will be updated.
    """
    code: Optional[str] = Field(None, max_length=32)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    pay_date: Optional[date] = None
    status: Optional[Status] = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("code cannot be empty when provided")
        return v

    @model_validator(mode="after")
    def _check_dates(self) -> "PayPeriodUpdate":
        # Only validate when the relevant fields are provided
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.start_date and self.pay_date and self.pay_date < self.start_date:
            raise ValueError("pay_date must be on or after start_date")
        return self


class PayPeriodOut(ORMBase):
    """
    Output model for responses.
    """
    id: str
    code: str
    start_date: date
    end_date: date
    pay_date: date
    status: Status
    created_at: datetime
    updated_at: datetime
    # If you later want nested runs, add:
    # runs: list["PayrollRunOut"] = []
    # and handle forward refs in your package's __init__.py

__all__ = [
    "PayPeriodCreate",
    "PayPeriodUpdate",
    "PayPeriodOut",
]
