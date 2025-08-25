# schemas/compliance_records.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel

from .base import ORMBase


class ComplianceRecordCreate(BaseModel):
    building_id: Optional[str] = None
    asset_id: Optional[str] = None
    record_type: str
    authority: Optional[str] = None
    identifier: Optional[str] = None
    issued_at: Optional[date] = None
    expires_at: Optional[date] = None
    documents: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None


class ComplianceRecordOut(ORMBase):
    id: str
    building_id: Optional[str] = None
    asset_id: Optional[str] = None
    record_type: str
    authority: Optional[str] = None
    identifier: Optional[str] = None
    issued_at: Optional[date] = None
    expires_at: Optional[date] = None
    documents: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
