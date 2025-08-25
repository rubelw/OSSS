# src/OSSS/schemas/asset.py

from __future__ import annotations

from datetime import date
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from .base import ORMModel


class AssetCreate(BaseModel):
    building_id: Optional[str] = None
    space_id: Optional[str] = None
    parent_asset_id: Optional[str] = None
    tag: str = Field(..., min_length=1)
    serial_no: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    install_date: Optional[date] = None
    warranty_expires_at: Optional[date] = None
    expected_life_months: Optional[int] = Field(None, ge=0)
    attributes: Optional[Dict[str, Any]] = None


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
