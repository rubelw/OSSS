# schemas/exportrun.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class ExportRunCreate(BaseModel):
    export_name: str
    ran_at: Optional[datetime] = None
    status: Optional[str] = "pending"
    file_uri: Optional[str] = None
    error: Optional[str] = None


class ExportRunOut(ORMBase):
    id: str
    export_name: str
    ran_at: datetime
    status: str
    file_uri: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
