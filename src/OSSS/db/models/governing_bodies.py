from __future__ import annotations

from typing import Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, TimestampMixin


class GoverningBody(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "governing_bodies"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=board_of_education_governing_board; "
        "description=Stores governing bodies records for the application. "
        "Key attributes include name. "
        "References related entities via: org. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "6 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores governing bodies records for the application. "
            "Key attributes include name. "
            "References related entities via: org. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores governing bodies records for the application. "
            "Key attributes include name. "
            "References related entities via: org. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    org_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    type: Mapped[Optional[str]] = mapped_column(sa.String(50))

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="governing_bodies",
        lazy="selectin",
    )

    # NEW: match Meeting.governing_body back_populates="meetings"
    meetings: Mapped[List["Meeting"]] = relationship(
        "Meeting",
        back_populates="governing_body",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
