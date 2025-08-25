from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from .base import ORMBase


class DeductionCodeCreate(ORMBase):
    code: str
    name: str
    pretax: Optional[bool] = True
    vendor_id: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class DeductionCodeOut(ORMBase):
    id: str
    code: str
    name: str
    pretax: bool
    vendor_id: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
