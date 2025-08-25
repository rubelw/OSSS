from __future__ import annotations

from datetime import datetime
from typing import Optional

from .base import ORMBase
from pydantic import BaseModel


class PersonContactCreate(BaseModel):
    person_id: str
    contact_id: str
    label: Optional[str] = None
    is_primary: bool = False
    is_emergency: bool = False


class PersonContactOut(ORMBase):
    person_id: str
    contact_id: str
    label: Optional[str] = None
    is_primary: bool
    is_emergency: bool
    created_at: datetime
    updated_at: datetime
