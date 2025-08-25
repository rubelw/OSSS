from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel

from .base import ORMBase


class GLSegmentCreate(BaseModel):
    type: str
    code: str
    name: str
    parent_id: Optional[str] = None
    active: bool = True
    attributes: Optional[Dict[str, Any]] = None


class GLSegmentUpdate(BaseModel):
    type: Optional[str] = None
    code: Optional[str] = None
    name: Optional[str] = None
    parent_id: Optional[str] = None
    active: Optional[bool] = None
    attributes: Optional[Dict[str, Any]] = None


class GLSegmentOut(ORMBase):
    id: str
    type: str
    code: str
    name: str
    parent_id: Optional[str] = None
    active: bool
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
