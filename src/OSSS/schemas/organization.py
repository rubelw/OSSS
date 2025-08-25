from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .base import ORMBase


class OrganizationCreate(BaseModel):
    name: str
    code: Optional[str] = None

class OrganizationOut(ORMBase):
    id: str
    name: str
    code: Optional[str] = None
    created_at: datetime
    updated_at: datetime
