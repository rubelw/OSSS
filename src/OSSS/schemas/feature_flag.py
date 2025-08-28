# OSSS/schemas/feature_flag.py
from __future__ import annotations
from typing import Optional, List
from pydantic import Field
from OSSS.schemas.base import APIModel

class FeatureFlagBase(APIModel):
    org_id: str = Field(...)
    key: str = Field(..., max_length=64)
    enabled: Optional[bool] = None  # let server_default apply if omitted

class FeatureFlagCreate(FeatureFlagBase): pass
class FeatureFlagReplace(FeatureFlagBase): pass

class FeatureFlagPatch(APIModel):
    org_id: Optional[str] = None
    key: Optional[str] = None
    enabled: Optional[bool] = None

class FeatureFlagOut(FeatureFlagBase):
    id: str

class FeatureFlagList(APIModel):
    items: List[FeatureFlagOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
