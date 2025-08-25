from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel

from .base import ORMBase


class MoveOrderCreate(BaseModel):
    project_id: Optional[str] = None
    person_id: Optional[str] = None
    from_space_id: Optional[str] = None
    to_space_id: Optional[str] = None
    move_date: Optional[date] = None
    status: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class MoveOrderOut(ORMBase):
    id: str
    project_id: Optional[str] = None
    person_id: Optional[str] = None
    from_space_id: Optional[str] = None
    to_space_id: Optional[str] = None
    move_date: Optional[date] = None
    status: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
