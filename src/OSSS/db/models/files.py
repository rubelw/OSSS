from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class File(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "files"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores files records for the application. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`."
    )

    __table_args__ = {
        "comment":         (
            "Stores files records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores files records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`."
        ),
        },
    }


    storage_key: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    filename: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    size: Mapped[Optional[int]] = mapped_column(sa.BigInteger)
    mime_type: Mapped[Optional[str]] = mapped_column(sa.String(127))
    created_by: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("users.id"))

    meeting_links: Mapped[list["MeetingFile"]] = relationship(
        "MeetingFile",
        back_populates="file",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    # 🔧 add this to match PolicyFile.file.back_populates="policy_links"
    policy_links: Mapped[list["PolicyFile"]] = relationship(
        "PolicyFile",
        back_populates="file",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

