# app/models/repo.py
# src/OSSS/db/model/repo.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Literal, List

import sqlalchemy as sa
from sqlalchemy import String, Boolean, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, GUID, TSVectorType, UUIDMixin, JSONB


# -------------------------------
# Folders
# -------------------------------
class Folder(UUIDMixin, Base):
    __tablename__ = "folders"

    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("folders.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    sort_order: Mapped[Optional[int]] = mapped_column(Integer)

    # relationships
    parent: Mapped[Optional["Folder"]] = relationship(
        "Folder",
        remote_side="Folder.id",
        back_populates="children",
        lazy="selectin",
    )
    children: Mapped[List["Folder"]] = relationship(
        "Folder",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="folder",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    __table_args__ = (Index("ix_folders_org", "org_id"),)


# -------------------------------
# Documents
# -------------------------------
class Document(UUIDMixin, Base):
    __tablename__ = "documents"

    folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("folders.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # FK is added via table-level constraint below (current_version_id -> document_versions.id)
    current_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), nullable=True)

    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))

    # relationships
    folder: Mapped[Optional["Folder"]] = relationship("Folder", back_populates="documents", lazy="selectin")

    # EXPLICIT: Document.id -> DocumentVersion.document_id
    versions: Mapped[List["DocumentVersion"]] = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="DocumentVersion.document_id",
        primaryjoin="Document.id == DocumentVersion.document_id",
        lazy="selectin",
    )

    # EXPLICIT: Document.current_version_id -> DocumentVersion.id
    # viewonly avoids write-order conflicts with versions
    current_version: Mapped[Optional["DocumentVersion"]] = relationship(
        "DocumentVersion",
        uselist=False,
        viewonly=True,
        foreign_keys=[current_version_id],
        primaryjoin="Document.current_version_id == DocumentVersion.id",
        lazy="joined",
    )

    notifications: Mapped[List["DocumentNotification"]] = relationship(
        "DocumentNotification",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    activities: Mapped[List["DocumentActivity"]] = relationship(
        "DocumentActivity",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    search_index: Mapped[Optional["DocumentSearchIndex"]] = relationship(
        "DocumentSearchIndex",
        back_populates="document",
        cascade="all, delete-orphan",
        uselist=False,
        passive_deletes=True,
        lazy="joined",
    )

    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["current_version_id"],
            ["document_versions.id"],
            name="fk_documents_current_version",
            ondelete="SET NULL",
        ),
    )


# -------------------------------
# Document Versions
# -------------------------------
class DocumentVersion(UUIDMixin, Base):
    __tablename__ = "document_versions"

    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    file_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("files.id", ondelete="RESTRICT"), nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(128))
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id"))

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))

    # EXPLICIT: tie back to Document
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="versions",
        foreign_keys=[document_id],
        primaryjoin="DocumentVersion.document_id == Document.id",
        lazy="joined",
    )


# -------------------------------
# Document Permissions
# -------------------------------
ResourceType = Literal["folder", "document"]
PrincipalType = Literal["user", "group", "role"]
PermissionType = Literal["view", "edit", "manage"]


class DocumentPermission(Base):
    __tablename__ = "document_permissions"

    resource_type: Mapped[str] = mapped_column(String(20), primary_key=True)   # folder|document
    resource_id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True)
    principal_type: Mapped[str] = mapped_column(String(20), primary_key=True)  # user|group|role
    principal_id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True)
    permission: Mapped[str] = mapped_column(String(20), primary_key=True)      # view|edit|manage
    # No FKs here by design (polymorphic target)


# -------------------------------
# Document Notifications
# -------------------------------
class DocumentNotification(Base):
    __tablename__ = "document_notifications"

    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    subscribed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))

    document: Mapped["Document"] = relationship("Document", back_populates="notifications", lazy="joined")


# -------------------------------
# Document Activity
# -------------------------------
class DocumentActivity(UUIDMixin, Base):
    __tablename__ = "document_activity"

    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    meta: Mapped[Optional[dict]] = mapped_column(JSONB())

    document: Mapped["Document"] = relationship("Document", back_populates="activities", lazy="joined")

    __table_args__ = (Index("ix_document_activity_doc", "document_id"),)


# -------------------------------
# Document Search Index (GIN)
# -------------------------------
class DocumentSearchIndex(Base):
    __tablename__ = "document_search_index"

    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    # With sqlalchemy-utils TSVectorType you can pass column names (e.g., TSVectorType('title'))
    # Our fallback maps to TSVECTOR on PG or TEXT elsewhere.
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())

    document: Mapped["Document"] = relationship("Document", back_populates="search_index", lazy="joined")

    __table_args__ = (
        sa.Index("ix_document_search_gin", "ts", postgresql_using="gin"),
    )
