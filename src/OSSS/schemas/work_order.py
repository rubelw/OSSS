from __future__ import annotations
from typing import Optional
from datetime import datetime
from .base import ORMModel

class WorkOrderOut(ORMModel):
    id: str
    school_id: Optional[str] = None
    building_id: Optional[str] = None
    space_id: Optional[str] = None
    asset_id: Optional[str] = None
    request_id: Optional[str] = None
    status: str
    priority: Optional[str] = None
    category: Optional[str] = None
    summary: str
    description: Optional[str] = None
    requested_due_at: Optional[datetime] = None
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assigned_to_user_id: Optional[str] = None
    materials_cost: Optional[float] = None
    labor_cost: Optional[float] = None
    other_cost: Optional[float] = None
    attributes: Optional[dict] = None
