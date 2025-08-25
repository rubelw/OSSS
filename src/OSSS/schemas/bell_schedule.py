from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .base import ORMBase


class BellScheduleCreate(BaseModel):
    school_id: str = Field(..., description="ID of the school this schedule belongs to")
    name: str = Field(..., min_length=1, max_length=255, description="Display name of the bell schedule")


class BellScheduleOut(ORMBase):
    id: str
    school_id: str
    name: str
    created_at: datetime
    updated_at: datetime
