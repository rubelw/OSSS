# schemas/warranty.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel
from .base import ORMBase


class WarrantyCreate(BaseModel):
    asset_id: str
    vendor_id: Optional[str] = None
    policy_no: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    terms: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class WarrantyOut(ORMBase):
    id: str
    asset_id: str
    vendor_id: Optional[str] = None
    policy_no: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    terms: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
