from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .base import ORMBase


class RoomCreate(BaseModel):
    school_id: str
    name: str
    capacity: Optional[int] = None


class RoomOut(ORMBase):
    id: str
    school_id: str
    name: str
    capacity: Optional[int] = None
    created_at: datetime
    updated_at: datetime
