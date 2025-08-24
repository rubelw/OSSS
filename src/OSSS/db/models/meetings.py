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
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    body_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("bodies.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    ends_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    location: Mapped[Optional[str]] = mapped_column(sa.String(255))
    status: Mapped[Optional[str]] = mapped_column(sa.String(32))
    is_public: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    stream_url: Mapped[Optional[str]] = mapped_column(sa.String(1024))

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

    __table_args__ = (
        sa.Index("ix_meetings_org", "org_id"),
        sa.Index("ix_meetings_body", "body_id"),
        sa.Index("ix_meetings_starts_at", "starts_at"),
    )
