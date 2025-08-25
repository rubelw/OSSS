from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class UserAccountCreate(BaseModel):
    person_id: str
    username: str
    is_active: bool = True


class UserAccountOut(ORMBase):
    id: str
    person_id: str
    username: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
