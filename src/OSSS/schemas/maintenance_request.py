from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from .base import ORMModel


class MaintenanceRequestCreate(BaseModel):
    school_id: Optional[str] = None
    building_id: Optional[str] = None
    space_id: Optional[str] = None
    asset_id: Optional[str] = None
    submitted_by_user_id: Optional[str] = None
    status: Optional[str] = "open"   # e.g., open|in_progress|closed
    priority: Optional[str] = None   # e.g., low|medium|high|urgent
    summary: str
    description: Optional[str] = None
    attributes: Optional[dict] = None


class MaintenanceRequestOut(ORMModel):
    id: str
    school_id: Optional[str] = None
    building_id: Optional[str] = None
    space_id: Optional[str] = None
    asset_id: Optional[str] = None
    submitted_by_user_id: Optional[str] = None
    status: str
    priority: Optional[str] = None
    summary: str
    description: Optional[str] = None
    converted_work_order_id: Optional[str] = None
    attributes: Optional[dict] = None
