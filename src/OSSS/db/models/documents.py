from __future__ import annotations

from typing import Optional, List, ClassVar
from datetime import datetime
import uuid
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB


class Document(UUIDMixin, Base):
    __tablename__ = "documents"
    __allow_unmapped__ = True  # ignore non-mapped constants, etc.

    NOTE: ClassVar[str] = (
        "owner=division_of_technology_data; "
        "description=Stores documents records for the application. "
        "Key attributes include title. References related entities via: current version, folder. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
    )

    # Add the FK constraint for current_version_id explicitly
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["current_version_id"],
            ["document_versions.id"],
            name="documents_current_version_id_fkey",
            ondelete="SET NULL",
        ),
        {
            "comment": (
                "Stores documents records for the application. Key attributes include title. "
                "References related entities via: current version, folder. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
            ),
            "info": {
                "note": NOTE,
                "description": (
                    "Stores documents records for the application. Key attributes include title. "
                    "References related entities via: current version, folder. "
                    "Includes standard audit timestamps (created_at, updated_at). "
                    "7 column(s) defined. Primary key is `id`. 2 foreign key field(s) detected."
                ),
            },
        },
    )

    folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), sa.ForeignKey("folders.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)

    # FK is enforced via __table_args__ above
    current_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), nullable=True, index=True)

    is_public: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.sql.false()
    )

    # relationships
    folder: Mapped[Optional["Folder"]] = relationship(
        "Folder", back_populates="documents", lazy="selectin"
    )

    # Document.id -> DocumentVersion.document_id
    versions: Mapped[List["DocumentVersion"]] = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="DocumentVersion.document_id",
        primaryjoin="Document.id == DocumentVersion.document_id",
        lazy="selectin",
    )

    # Document.current_version_id -> DocumentVersion.id (view-only for safety)
    current_version: Mapped[Optional["DocumentVersion"]] = relationship(
        "DocumentVersion",
        uselist=False,
        viewonly=True,
        foreign_keys=[current_version_id],
        primaryjoin="Document.current_version_id == DocumentVersion.id",
        lazy="joined",
    )

    # NEW: reverse link to ProposalDocument
    proposal_links: Mapped[List["ProposalDocument"]] = relationship(
        "ProposalDocument",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
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
