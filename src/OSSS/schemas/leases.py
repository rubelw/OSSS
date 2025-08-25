from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from pydantic import BaseModel

from .base import ORMBase


class LeaseCreate(BaseModel):
    building_id: Optional[str] = None
    landlord: Optional[str] = None
    tenant: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    base_rent: Optional[Decimal] = None
    rent_schedule: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None
    documents: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None


class LeaseOut(ORMBase):
    id: str
    building_id: Optional[str] = None
    landlord: Optional[str] = None
    tenant: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    base_rent: Optional[Decimal] = None
    rent_schedule: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None
    documents: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
