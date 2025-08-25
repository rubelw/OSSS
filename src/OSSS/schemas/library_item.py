from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .base import ORMBase


class LibraryItemCreate(BaseModel):
    school_id: str
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    barcode: Optional[str] = None


class LibraryItemOut(ORMBase):
    id: str
    school_id: str
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    barcode: Optional[str] = None
    created_at: datetime
    updated_at: datetime
