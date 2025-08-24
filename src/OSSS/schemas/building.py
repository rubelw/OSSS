from __future__ import annotations
from typing import Optional
from .base import ORMModel

class BuildingOut(ORMModel):
    id: str
    facility_id: str
    name: str
    code: Optional[str] = None
    year_built: Optional[int] = None
    floors_count: Optional[int] = None
    gross_sqft: Optional[float] = None
    use_type: Optional[str] = None
    address: Optional[dict] = None
    attributes: Optional[dict] = None
