from __future__ import annotations
from typing import Optional
from .base import ORMModel

class FloorOut(ORMModel):
    id: str
    building_id: str
    level_code: str
    name: Optional[str] = None
