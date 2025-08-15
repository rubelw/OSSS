from __future__ import annotations
from datetime import datetime, date

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Integer, Text, ForeignKey, TIMESTAMP
from .base import Base, UUIDMixin, GUID, JSONB, TSVectorType
import uuid


class Folder(UUIDMixin, Base):
    __tablename__ = "folders"
    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("folders.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[Optional[int]] = mapped_column(Integer)

class Document(UUIDMixin, Base):
    __tablename__ = "documents"
    folder_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("folders.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    current_version_id: Mapped[Optional[str]] = mapped_column(GUID())
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

class DocumentVersion(UUIDMixin, Base):
    __tablename__ = "document_versions"
    document_id: Mapped[str] = mapped_column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    file_id: Mapped[str] = mapped_column(GUID(), ForeignKey("files.id", ondelete="RESTRICT"), nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(128))
    created_by: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)  # type: ignore
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))  # type: ignore

class DocumentPermission(Base):
    __tablename__ = "document_permissions"
    resource_type: Mapped[str] = mapped_column(String(20), primary_key=True)  # folder|document
    resource_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    principal_type: Mapped[str] = mapped_column(String(20), primary_key=True)  # user|group|role
    principal_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    permission: Mapped[str] = mapped_column(String(20), primary_key=True)  # view|edit|manage

class DocumentNotification(Base):
    __tablename__ = "document_notifications"
    document_id: Mapped[str] = mapped_column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    subscribed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))  # type: ignore

class DocumentActivity(UUIDMixin, Base):
    __tablename__ = "document_activity"
    document_id: Mapped[str] = mapped_column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)  # type: ignore
    meta: Mapped[Optional[dict]] = mapped_column(JSONB())

class DocumentSearchIndex(Base):
    __tablename__ = "document_search_index"
    document_id: Mapped[str] = mapped_column(GUID(), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())
