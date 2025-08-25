from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from pydantic import BaseModel

from .base import ORMBase


class MeterCreate(BaseModel):
    asset_id: Optional[str] = None
    building_id: Optional[str] = None
    name: str
    meter_type: Optional[str] = None
    uom: Optional[str] = None
    last_read_value: Optional[Decimal] = None
    last_read_at: Optional[datetime] = None
    attributes: Optional[Dict[str, Any]] = None


class MeterOut(ORMBase):
    id: str
    asset_id: Optional[str] = None
    building_id: Optional[str] = None
    name: str
    meter_type: Optional[str] = None
    uom: Optional[str] = None
    last_read_value: Optional[Decimal] = None
    last_read_at: Optional[datetime] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
