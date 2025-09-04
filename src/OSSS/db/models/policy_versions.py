from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class PolicyVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "policy_versions"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=special_education_related_services; "
        "description=Stores policy versions records for the application. "
        "References related entities via: policy, supersedes version. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "9 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores policy versions records for the application. "
            "References related entities via: policy, supersedes version. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores policy versions records for the application. "
            "References related entities via: policy, supersedes version. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    policy_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    content: Mapped[Optional[str]] = mapped_column(sa.Text)
    effective_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    supersedes_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("policy_versions.id", ondelete="SET NULL")
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("users.id")
    )

    policy: Mapped["Policy"] = relationship(
        "Policy", back_populates="versions", lazy="joined"
    )
    supersedes: Mapped[Optional["PolicyVersion"]] = relationship(
        "PolicyVersion",
        remote_side="PolicyVersion.id",
        lazy="joined",
        viewonly=True,
    )

    # 🔧 reverse side for PolicyFile.policy_version (back_populates="files")
    files: Mapped[list["PolicyFile"]] = relationship(
        "PolicyFile",
        back_populates="policy_version",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
