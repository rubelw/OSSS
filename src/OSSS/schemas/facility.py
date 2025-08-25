from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from .base import ORMModel


class FacilityCreate(BaseModel):
    school_id: str
    name: str
    code: Optional[str] = None
    address: Optional[dict] = None
    attributes: Optional[dict] = None


class FacilityOut(ORMModel):
    id: str
    school_id: str
    name: str
    code: Optional[str] = None
    address: Optional[dict] = None
    attributes: Optional[dict] = None
