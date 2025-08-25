from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .base import ORMBase


class AddressCreate(BaseModel):
    line1: str
    line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class AddressOut(ORMBase):
    id: str
    line1: str
    line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    created_at: datetime
    updated_at: datetime
