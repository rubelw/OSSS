# src/OSSS/db/models/documents.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, List

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, GUID, UUIDMixin, JSONB, TSVectorType


# -------------------------------
# Folders
# -------------------------------
class Folder(UUIDMixin, Base):
    __tablename__ = "folders"

    org_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[Optional[str]] = mapped_column(
        GUID(), sa.ForeignKey("folders.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    is_public: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))
    sort_order: Mapped[Optional[int]] = mapped_column(sa.Integer)

    # relationships
    parent: Mapped[Optional["Folder"]] = relationship(
        "Folder",
        remote_side=lambda: [Folder.id],
        back_populates="children",
        foreign_keys=lambda: [Folder.parent_id],
    )
    children: Mapped[List["Folder"]] = relationship(
        "Folder",
        back_populates="parent",
        foreign_keys=lambda: [Folder.parent_id],
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="folder", cascade="all, delete-orphan", passive_deletes=True
    )


# -------------------------------
# Documents
# -------------------------------
class Document(UUIDMixin, Base):
    __tablename__ = "documents"

    folder_id: Mapped[Optional[str]] = mapped_column(
        GUID(), sa.ForeignKey("folders.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    # FK created below in __table_args__ to match migration pattern
    current_version_id: Mapped[Optional[str]] = mapped_column(GUID(), nullable=True)
    is_public: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))

    # relationships
    folder: Mapped[Optional["Folder"]] = relationship("Folder", back_populates="documents")

    versions: Mapped[List["DocumentVersion"]] = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="DocumentVersion.document_id",
        primaryjoin="Document.id == DocumentVersion.document_id",
    )

    # read-only pointer to the current version
    current_version: Mapped[Optional["DocumentVersion"]] = relationship(
        "DocumentVersion",
        uselist=False,
        viewonly=True,
        foreign_keys=lambda: [Document.current_version_id],
        primaryjoin=lambda: Document.current_version_id == DocumentVersion.id,
        lazy="joined",
    )

    notifications: Mapped[List["DocumentNotification"]] = relationship(
        "DocumentNotification", back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
    activities: Mapped[List["DocumentActivity"]] = relationship(
        "DocumentActivity", back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
    search_index: Mapped[Optional["DocumentSearchIndex"]] = relationship(
        "DocumentSearchIndex", back_populates="document", cascade="all, delete-orphan", uselist=False, passive_deletes=True
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

    document_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    file_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("files.id", ondelete="RESTRICT"), nullable=False
    )
    checksum: Mapped[Optional[str]] = mapped_column(sa.String(128))
    created_by: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="versions",
        foreign_keys=lambda: [DocumentVersion.document_id],
        primaryjoin=lambda: DocumentVersion.document_id == Document.id,
    )


# -------------------------------
# Document Permissions
# -------------------------------
class DocumentPermission(Base):
    __tablename__ = "document_permissions"

    resource_type: Mapped[str] = mapped_column(sa.String(20), primary_key=True)   # folder|document
    resource_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    principal_type: Mapped[str] = mapped_column(sa.String(20), primary_key=True)  # user|group|role
    principal_id: Mapped[str] = mapped_column(GUID(), primary_key=True)
    permission: Mapped[str] = mapped_column(sa.String(20), primary_key=True)      # view|edit|manage
    # (polymorphic, so no FKs by design)


# -------------------------------
# Notifications
# -------------------------------
class DocumentNotification(Base):
    __tablename__ = "document_notifications"

    document_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    subscribed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))

    document: Mapped["Document"] = relationship("Document", back_populates="notifications")


# -------------------------------
# Activity
# -------------------------------
class DocumentActivity(UUIDMixin, Base):
    __tablename__ = "document_activity"

    document_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))
    meta: Mapped[Optional[dict]] = mapped_column(JSONB())

    document: Mapped["Document"] = relationship("Document", back_populates="activities")

    __table_args__ = (sa.Index("ix_document_activity_doc", "document_id"),)


# -------------------------------
# Full-Text Search (GIN)
# -------------------------------
class DocumentSearchIndex(Base):
    __tablename__ = "document_search_index"

    document_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())

    document: Mapped["Document"] = relationship("Document", back_populates="search_index")

    __table_args__ = (
        sa.Index("ix_document_search_gin", "ts", postgresql_using="gin"),
    )

