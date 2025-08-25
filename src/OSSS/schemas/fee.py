from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Any, Dict
from pydantic import BaseModel

from .base import ORMBase


class FeeCreate(BaseModel):
    school_id: str
    name: str
    amount: Decimal


class FeeOut(ORMBase):
    id: str
    school_id: str
    name: str
    amount: Decimal
    created_at: datetime
    updated_at: datetime
