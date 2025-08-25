from __future__ import annotations

from datetime import datetime
from typing import Optional

from .base import ORMBase
from pydantic import BaseModel


class PersonAddressCreate(BaseModel):
    person_id: str
    address_id: str
    is_primary: bool = False


class PersonAddressOut(ORMBase):
    person_id: str
    address_id: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime
