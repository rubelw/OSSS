# OSSS/schemas/ap_vendors.py
from __future__ import annotations

from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

from pydantic import Field
from OSSS.schemas.base import APIModel


class ApVendorBase(APIModel):
    vendor_no: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=64)

    # JSON/JSONB-ish fields are represented as dicts in the API
    remit_to: Optional[Dict[str, Any]] = None
    contact: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None

    # Model default is true at the DB level; mirror that here
    active: bool = True


class ApVendorCreate(ApVendorBase):
    """Payload to create an AP vendor."""
    pass


class ApVendorUpdate(APIModel):
    """Partial update; send only fields that should change."""
    vendor_no: Optional[str] = Field(None, min_length=1, max_length=64)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=64)

    remit_to: Optional[Dict[str, Any]] = None
    contact: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None

    active: Optional[bool] = None


class ApVendorOut(ApVendorBase):
    """Response model."""
    id: UUID
    created_at: datetime
    updated_at: datetime


ApVendorList = List[ApVendorOut]

__all__ = [
    "ApVendorBase",
    "ApVendorCreate",
    "ApVendorUpdate",
    "ApVendorOut",
    "ApVendorList",
]
