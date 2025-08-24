from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from .base import ORMBase

class GlSegmentBase(ORMBase):
    type: str
    code: str
    name: str
    parent_id: Optional[str] = None
    active: bool = True
    attributes: Optional[Dict[str, Any]] = None

class GlSegmentCreate(GlSegmentBase):
    pass

class GlSegmentUpdate(ORMBase):
    type: Optional[str] = None
    code: Optional[str] = None
    name: Optional[str] = None
    parent_id: Optional[str] = None
    active: Optional[bool] = None
    attributes: Optional[Dict[str, Any]] = None

class GlSegmentOut(GlSegmentBase):
    id: str
    created_at: datetime
    updated_at: datetime
