# OSSS/schemas/asset_part.py
from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import Field
from OSSS.schemas.base import APIModel

class AssetPartBase(APIModel):
    asset_id: str = Field(...)
    part_id:  str = Field(...)
    qty: Optional[Decimal] = None  # let server_default=1 apply if omitted

class AssetPartCreate(AssetPartBase): pass
class AssetPartReplace(AssetPartBase):
    qty: Decimal = Field(...)

class AssetPartPatch(APIModel):
    asset_id: Optional[str] = None
    part_id:  Optional[str] = None
    qty: Optional[Decimal] = None

class AssetPartOut(AssetPartBase):
    id: str
    created_at: datetime
    updated_at: datetime

class AssetPartList(APIModel):
    items: List[AssetPartOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
