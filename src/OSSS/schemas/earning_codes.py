from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel

from .base import ORMBase


class EarningCodeCreate(BaseModel):
    code: str
    name: str
    taxable: Optional[bool] = True
    attributes: Optional[Dict[str, Any]] = None


class EarningCodeOut(ORMBase):
    id: str
    code: str
    name: str
    taxable: bool
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
