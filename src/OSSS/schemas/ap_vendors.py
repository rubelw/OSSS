# OSSS/schemas/ap_vendors.py
from __future__ import annotations

from typing import Optional, Dict, Any, List
from pydantic import Field
from OSSS.schemas.base import APIModel


class ApVendorBase(APIModel):
    vendor_no: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=64)

    remit_to: Optional[Dict[str, Any]] = None
    contact: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None

    active: Optional[bool] = True


class ApVendorCreate(ApVendorBase):
    pass


class ApVendorUpdate(APIModel):
    vendor_no: Optional[str] = Field(None, min_length=1, max_length=64)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=64)

    remit_to: Optional[Dict[str, Any]] = None
    contact: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None

    active: Optional[bool] = None


class ApVendorOut(ApVendorBase):
    id: str
    # If your mixins add timestamps, include them:
    # created_at: datetime
    # updated_at: datetime


ApVendorList = List[ApVendorOut]

__all__ = [
    "ApVendorBase",
    "ApVendorCreate",
    "ApVendorUpdate",
    "ApVendorOut",
    "ApVendorList",
]
