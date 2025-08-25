from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from .base import ORMModel


class FloorCreate(BaseModel):
    building_id: str
    level_code: str
    name: Optional[str] = None


class FloorOut(ORMModel):
    id: str
    building_id: str
    level_code: str
    name: Optional[str] = None
