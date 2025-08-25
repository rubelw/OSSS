# src/OSSS/schemas/asset_part.py

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field

from .base import ORMModel


class AssetPartCreate(BaseModel):
    asset_id: str
    part_id: str
    qty: Decimal = Field(default=Decimal("1"), ge=Decimal("0"))


class AssetPartOut(ORMModel):
    asset_id: str
    part_id: str
    qty: Decimal
    created_at: datetime
    updated_at: datetime
