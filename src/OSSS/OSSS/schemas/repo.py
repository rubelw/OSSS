from __future__ import annotations
from typing import Optional, List
from datetime import datetime

from .base import ORMModel, TimestampMixin


class RepoFolderBase(ORMModel):
    org_id: str
    name: str
    parent_id: Optional[str] = None
    is_public: bool = False
    sort_order: Optional[int] = None


class RepoFolderOut(RepoFolderBase, TimestampMixin):
    id: str


class RepoDocumentBase(ORMModel):
    title: str
    folder_id: Optional[str] = None
    current_version_id: Optional[str] = None
    is_public: bool = False


class RepoDocumentOut(RepoDocumentBase, TimestampMixin):
    id: str


class RepoDocumentVersionOut(ORMModel):
    id: str
    document_id: str
    version_no: int
    file_id: str
    checksum: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    published_at: Optional[datetime] = None


class RepoDocumentNotificationOut(ORMModel):
    document_id: str
    user_id: str
    subscribed: bool
    last_sent_at: Optional[datetime] = None


class RepoDocumentActivityOut(ORMModel):
    id: str
    document_id: str
    actor_id: Optional[str] = None
    action: str
    at: datetime
    meta: Optional[dict] = None


class RepoDocumentSearchIndexOut(ORMModel):
    document_id: str
    ts: Optional[str] = None
