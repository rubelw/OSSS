from __future__ import annotations
from typing import Optional
from datetime import date, datetime

from .base import ORMModel


class FacilityOut(ORMModel):
    id: str
    school_id: str
    name: str
    code: Optional[str] = None
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


class FloorOut(ORMModel):
    id: str
    building_id: str
    level_code: str
    name: Optional[str] = None


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


class AssetOut(ORMModel):
    id: str
    building_id: Optional[str] = None
    space_id: Optional[str] = None
    parent_asset_id: Optional[str] = None
    tag: str
    serial_no: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    install_date: Optional[date] = None
    warranty_expires_at: Optional[date] = None
    expected_life_months: Optional[int] = None
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
