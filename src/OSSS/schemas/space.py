from __future__ import annotations

from typing import Optional, Dict, Any
from pydantic import BaseModel
from .base import ORMModel


class SpaceCreate(BaseModel):
    building_id: str
    floor_id: Optional[str] = None
    code: str
    name: Optional[str] = None
    space_type: Optional[str] = None
    area_sqft: Optional[float] = None
    capacity: Optional[int] = None
    attributes: Optional[Dict[str, Any]] = None


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
