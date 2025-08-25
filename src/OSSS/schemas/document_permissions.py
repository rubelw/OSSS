from __future__ import annotations

from typing import Literal
from pydantic import BaseModel

from .base import ORMBase


class DocumentPermissionCreate(BaseModel):
    resource_type: Literal["folder", "document"]
    resource_id: str
    principal_type: Literal["user", "group", "role"]
    principal_id: str
    permission: str  # e.g., "view", "edit", "manage"


class DocumentPermissionOut(ORMBase):
    resource_type: str
    resource_id: str
    principal_type: str
    principal_id: str
    permission: str
