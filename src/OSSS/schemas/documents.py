from __future__ import annotations
from typing import Optional, List
from datetime import datetime

from .base import ORMModel, TimestampMixin


class FolderBase(ORMModel):
    org_id: str
    name: str
    parent_id: Optional[str] = None
    is_public: bool = False
    sort_order: Optional[int] = None


class FolderCreate(FolderBase):
    pass


class FolderOut(FolderBase, TimestampMixin):
    id: str


class DocumentBase(ORMModel):
    title: str
    folder_id: Optional[str] = None
    current_version_id: Optional[str] = None
    is_public: bool = False


class DocumentCreate(DocumentBase):
    pass


class DocumentOut(DocumentBase, TimestampMixin):
    id: str


class DocumentVersionBase(ORMModel):
    document_id: str
    version_no: int = 1
    file_id: str
    checksum: Optional[str] = None
    created_by: Optional[str] = None
    published_at: Optional[datetime] = None


class DocumentVersionCreate(DocumentVersionBase):
    pass


class DocumentVersionOut(DocumentVersionBase, TimestampMixin):
    id: str
    created_at: datetime


class DocumentPermissionOut(ORMModel):
    resource_type: str
    resource_id: str
    principal_type: str
    principal_id: str
    permission: str


class DocumentNotificationOut(ORMModel):
    document_id: str
    user_id: str
    subscribed: bool
    last_sent_at: Optional[datetime] = None


class DocumentActivityOut(ORMModel):
    id: str
    document_id: str
    actor_id: Optional[str] = None
    action: str
    at: datetime
    meta: Optional[dict] = None


class DocumentSearchIndexOut(ORMModel):
    document_id: str
    ts: Optional[str] = None
