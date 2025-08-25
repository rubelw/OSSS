from __future__ import annotations

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel

from .base import ORMBase


class GLAccountCreate(BaseModel):
    number: str
    name: str
    natural_class: Optional[str] = None  # asset|liability|equity|revenue|expense
    is_postable: bool = True
    active: bool = True
    segments_json: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None


class GLAccountUpdate(BaseModel):
    number: Optional[str] = None
    name: Optional[str] = None
    natural_class: Optional[str] = None
    is_postable: Optional[bool] = None
    active: Optional[bool] = None
    segments_json: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None


class GLAccountOut(ORMBase):
    id: str
    number: str
    name: str
    natural_class: Optional[str] = None
    is_postable: bool
    active: bool
    segments_json: Optional[Dict[str, Any]] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
