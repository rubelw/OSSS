# schemas/payroll_runs.py
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field, field_validator

from .base import ORMBase  # should set: model_config = ConfigDict(from_attributes=True)


_ALLOWED_STATUS = ("open", "processed", "posted")


class PayrollRunBase(ORMBase):
    pay_period_id: str
    run_no: int = Field(1, ge=1, description="Sequence within the pay period (>= 1)")
    status: Literal["open", "processed", "posted"] = "open"
    created_by_user_id: Optional[str] = None
    posted_entry_id: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _normalize_status(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in _ALLOWED_STATUS:
            raise ValueError(f"status must be one of {_ALLOWED_STATUS}")
        return v


class PayrollRunCreate(PayrollRunBase):
    """Payload to create a payroll run."""
    pass


class PayrollRunUpdate(ORMBase):
    """Partial update for a payroll run; all fields optional."""
    pay_period_id: Optional[str] = None
    run_no: Optional[int] = Field(None, ge=1)
    status: Optional[Literal["open", "processed", "posted"]] = None
    created_by_user_id: Optional[str] = None
    posted_entry_id: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _normalize_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if v not in _ALLOWED_STATUS:
            raise ValueError(f"status must be one of {_ALLOWED_STATUS}")
        return v


class PayrollRunOut(ORMBase):
    id: str
    pay_period_id: str
    run_no: int
    status: Literal["open", "processed", "posted"]
    created_by_user_id: Optional[str] = None
    posted_entry_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


__all__ = ["PayrollRunCreate", "PayrollRunUpdate", "PayrollRunOut"]
