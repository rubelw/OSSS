from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional, Any, Dict

from pydantic import BaseModel, Field

from .base import ORMBase


class BusStopCreate(BaseModel):
    route_id: str = Field(..., description="FK to the bus route")
    name: str = Field(..., min_length=1, max_length=255)
    # Optional coordinates; validate plausible ranges
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180)


class BusStopOut(ORMBase):
    id: str
    route_id: str
    name: str
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
