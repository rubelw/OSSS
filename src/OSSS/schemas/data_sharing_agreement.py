from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class DataSharingAgreementCreate(BaseModel):
    vendor: str
    scope: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None


class DataSharingAgreementOut(ORMBase):
    id: str
    vendor: str
    scope: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
