# OSSS/schemas/role_permission.py
from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from pydantic import Field
from OSSS.schemas.base import APIModel

class RolePermissionBase(APIModel):
    role_id: str = Field(...)
    permission_id: str = Field(...)

class RolePermissionCreate(RolePermissionBase): pass
class RolePermissionReplace(RolePermissionBase): pass

class RolePermissionPatch(APIModel):
    role_id: Optional[str] = None
    permission_id: Optional[str] = None

class RolePermissionOut(RolePermissionBase):
    id: str
    created_at: datetime
    updated_at: datetime

class RolePermissionList(APIModel):
    items: List[RolePermissionOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
