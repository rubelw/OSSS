# schemas/vendor.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel
from .base import ORMBase


class VendorCreate(BaseModel):
    name: str
    contact: Optional[Dict[str, Any]] = None
    active: bool = True
    notes: Optional[str] = None


class VendorOut(ORMBase):
    id: str
    name: str
    contact: Optional[Dict[str, Any]] = None
    active: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
