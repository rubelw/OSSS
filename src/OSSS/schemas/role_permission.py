from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from .base import ORMBase


class RolePermissionCreate(BaseModel):
    role_id: str
    permission_id: str


class RolePermissionOut(ORMBase):
    role_id: str
    permission_id: str
    created_at: datetime
    updated_at: datetime
