from __future__ import annotations

from datetime import date
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class InitiativeCreate(BaseModel):
    objective_id: str
    name: str
    description: Optional[str] = None
    owner_id: Optional[str] = None
    due_date: Optional[date] = None
    status: Optional[str] = None
    priority: Optional[str] = None


class InitiativeOut(ORMBase):
    id: str
    objective_id: str
    name: str
    description: Optional[str] = None
    owner_id: Optional[str] = None
    due_date: Optional[date] = None
    status: Optional[str] = None
    priority: Optional[str] = None
