from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class FeatureFlagCreate(BaseModel):
    org_id: str
    key: str
    enabled: Optional[bool] = False


class FeatureFlagOut(ORMBase):
    org_id: str
    key: str
    enabled: bool
