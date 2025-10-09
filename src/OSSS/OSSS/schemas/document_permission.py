# OSSS/schemas/document_permission.py
from __future__ import annotations
from typing import Optional, List
from pydantic import Field
from OSSS.schemas.base import APIModel

class DocumentPermissionBase(APIModel):
    resource_type: str = Field(..., max_length=20)
    resource_id: str = Field(...)
    principal_type: str = Field(..., max_length=20)
    principal_id: str = Field(...)
    permission: str = Field(..., max_length=20)

class DocumentPermissionCreate(DocumentPermissionBase): pass
class DocumentPermissionReplace(DocumentPermissionBase): pass

class DocumentPermissionPatch(APIModel):
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    principal_type: Optional[str] = None
    principal_id: Optional[str] = None
    permission: Optional[str] = None

class DocumentPermissionOut(DocumentPermissionBase):
    id: str

class DocumentPermissionList(APIModel):
    items: List[DocumentPermissionOut]
    total: int | None = None
    skip: int = 0
    limit: int = 100
