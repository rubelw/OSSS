from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Any, Dict
from pydantic import BaseModel

from .base import ORMBase


class PartCreate(BaseModel):
    sku: Optional[str] = None
    name: str
    description: Optional[str] = None
    unit_cost: Optional[Decimal] = None
    uom: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class PartOut(ORMBase):
    id: str
    sku: Optional[str] = None
    name: str
    description: Optional[str] = None
    unit_cost: Optional[Decimal] = None
    uom: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
