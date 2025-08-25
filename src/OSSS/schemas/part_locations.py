from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class PartLocationCreate(BaseModel):
    part_id: str
    building_id: Optional[str] = None
    space_id: Optional[str] = None
    location_code: Optional[str] = None
    qty_on_hand: Optional[Decimal] = None
    min_qty: Optional[Decimal] = None
    max_qty: Optional[Decimal] = None


class PartLocationOut(ORMBase):
    id: str
    part_id: str
    building_id: Optional[str] = None
    space_id: Optional[str] = None
    location_code: Optional[str] = None
    qty_on_hand: Decimal
    min_qty: Optional[Decimal] = None
    max_qty: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
