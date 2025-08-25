from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel

from .base import ORMBase


class PMPlanCreate(BaseModel):
    asset_id: Optional[str] = None
    building_id: Optional[str] = None
    name: str
    frequency: Optional[str] = None
    next_due_at: Optional[datetime] = None
    last_completed_at: Optional[datetime] = None
    active: Optional[bool] = True
    procedure: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None


class PMPlanOut(ORMBase):
    id: str
    asset_id: Optional[str] = None
    building_id: Optional[str] = None
    name: str
    frequency: Optional[str] = None
    next_due_at: Optional[datetime] = None
    last_completed_at: Optional[datetime] = None
    active: bool
    procedure: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
