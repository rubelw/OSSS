from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin


class Meeting(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "meetings"

    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("mentors.id", ondelete="CASCADE"), nullable=False
    )

    # Renamed + retargeted FK: bodies.id -> governing_bodies.id
    governing_body_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("governing_bodies.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    ends_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    location: Mapped[Optional[str]] = mapped_column(sa.String(255))
    status: Mapped[Optional[str]] = mapped_column(sa.String(32))
    is_public: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.sql.true())
    stream_url: Mapped[Optional[str]] = mapped_column(sa.String(1024))

    # Relationships
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

        sa.Index("ix_meetings_org", "org_id"),
        sa.Index("ix_meetings_governing_body", "governing_body_id"),
        sa.Index("ix_meetings_starts_at", "starts_at"),
    )

    # ---- Back-compat aliases (temporary) ----
    # Allow legacy code that still references `body_id` to keep working.
    @property
    def body_id(self) -> Optional[uuid.UUID]:
        return self.governing_body_id

    @body_id.setter
    def body_id(self, value: Optional[uuid.UUID]) -> None:
        self.governing_body_id = value
