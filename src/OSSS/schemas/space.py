from __future__ import annotations
from typing import Optional
from .base import ORMModel

class SpaceOut(ORMModel):
    id: str
    building_id: str
    floor_id: Optional[str] = None
    code: str
    name: Optional[str] = None
    space_type: Optional[str] = None
    area_sqft: Optional[float] = None
    capacity: Optional[int] = None
    attributes: Optional[dict] = None
