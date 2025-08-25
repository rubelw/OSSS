from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, conint, confloat

from .base import ORMModel


class BuildingCreate(BaseModel):
    facility_id: str = Field(..., description="ID of the parent facility")
    name: str = Field(..., min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=50)
    year_built: Optional[conint(ge=1800, le=2100)] = None
    floors_count: Optional[conint(ge=0)] = None
    gross_sqft: Optional[confloat(ge=0)] = None
    use_type: Optional[str] = Field(None, max_length=100)
    address: Optional[dict] = None
    attributes: Optional[dict] = None


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
