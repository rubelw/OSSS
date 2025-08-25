from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from .base import ORMBase
from pydantic import BaseModel


class PersonCreate(BaseModel):
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    dob: Optional[date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None


class PersonOut(ORMBase):
    id: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    dob: Optional[date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    created_at: datetime
    updated_at: datetime
