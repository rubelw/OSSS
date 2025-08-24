from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List
import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Document(UUIDMixin, Base):
    __tablename__ = "documents"


    folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("folders.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)

    # FK is added via table-level constraint below (current_version_id -> document_versions.id)
    current_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), nullable=True)

    is_public: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))

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
