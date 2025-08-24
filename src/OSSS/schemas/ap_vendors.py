from __future__ import annotations
from typing import Optional, Dict, Any
from datetime import datetime
from .base import ORMBase

class ApVendorBase(ORMBase):
    vendor_no: Optional[str] = None
    name: str
    tax_id: Optional[str] = None
    remit_to: Optional[Dict[str, Any]] = None
    contact: Optional[Dict[str, Any]] = None
    active: bool = True
    attributes: Optional[Dict[str, Any]] = None

class ApVendorCreate(ApVendorBase):
    pass

class ApVendorUpdate(ORMBase):
    vendor_no: Optional[str] = None
    name: Optional[str] = None
    tax_id: Optional[str] = None
    remit_to: Optional[Dict[str, Any]] = None
    contact: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None
    attributes: Optional[Dict[str, Any]] = None

class ApVendorOut(ApVendorBase):
    id: str
    created_at: datetime
    updated_at: datetime
