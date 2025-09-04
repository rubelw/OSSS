from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin, ts_cols


class Meeting(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "meetings"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=special_education_related_services; "
        "description=Stores meetings records for the application. "
        "Key attributes include title. "
        "References related entities via: governing body, org. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "12 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores meetings records for the application. "
            "Key attributes include title. "
            "References related entities via: governing body, org. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "12 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores meetings records for the application. "
            "Key attributes include title. "
            "References related entities via: governing body, org. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "12 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Renamed + retargeted FK: bodies.id -> governing_bodies.id
    governing_body_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("governing_bodies.id", ondelete="SET NULL"), nullable=True
    )

    committee_id = sa.Column(GUID(), ForeignKey("committees.id", ondelete="CASCADE"), nullable=False)

    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    scheduled_at = sa.Column(sa.TIMESTAMP(timezone=True), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    ends_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    location: Mapped[Optional[str]] = mapped_column(sa.String(255))
    status: Mapped[Optional[str]] = mapped_column(sa.String(32))
    is_public: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.sql.true())
    stream_url: Mapped[Optional[str]] = mapped_column(sa.String(1024))

    created_at, updated_at = ts_cols()

    # Relationships
    committee      = relationship("Committee", back_populates="meetings")
    resolutions    = relationship("Resolution",     back_populates="meeting",   cascade="all, delete-orphan")
    publications   = relationship("Publication",    back_populates="meeting",   cascade="all, delete-orphan")
    meeting_documents = relationship("MeetingDocument", back_populates="meeting", cascade="all, delete-orphan")


    governing_body: Mapped[Optional["GoverningBody"]] = relationship(
        "GoverningBody",
        back_populates="meetings",
        lazy="selectin",
        passive_deletes=True,
    )

    agenda_items: Mapped[List["AgendaItem"]] = relationship(
        "AgendaItem",
        back_populates="meeting",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AgendaItem.position",
        lazy="selectin",
    )
    minutes: Mapped[List["Minutes"]] = relationship(
        "Minutes",
        back_populates="meeting",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Minutes.created_at",
        lazy="selectin",
    )
    permissions: Mapped[list["MeetingPermission"]] = relationship(
        "MeetingPermission",
        back_populates="meeting",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    files: Mapped[list["MeetingFile"]] = relationship(
        "MeetingFile",
        back_populates="meeting",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    attendance: Mapped[list["Attendance"]] = relationship(
        "Attendance",
        back_populates="meeting",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    @property
    def body_id(self) -> Optional[uuid.UUID]:
        return self.governing_body_id

    @body_id.setter
    def body_id(self, value: Optional[uuid.UUID]) -> None:
        self.governing_body_id = value