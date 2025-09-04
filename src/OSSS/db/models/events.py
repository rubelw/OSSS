from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class Event(UUIDMixin, Base):
    __tablename__ = "events"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores events records for the application. "
        "Key attributes include title. "
        "References related entities via: activity, school. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "12 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores events records for the application. "
            "Key attributes include title. "
            "References related entities via: activity, school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "12 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores events records for the application. "
            "Key attributes include title. "
            "References related entities via: activity, school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "12 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    school_id: Mapped[str] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    activity_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("activities.id", ondelete="SET NULL"))

    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(sa.Text)
    starts_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    ends_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    venue: Mapped[Optional[str]] = mapped_column(sa.String(255))
    status: Mapped[str] = mapped_column(sa.String(16), server_default=text("'draft'"), nullable=False)  # draft|published|cancelled
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    created_at, updated_at = ts_cols()

    activity: Mapped[Optional[Activity]] = relationship(back_populates="events")

    # ✅ one-to-many to TicketType
    ticket_types: Mapped[List["TicketType"]] = relationship(
        "TicketType",
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    orders: Mapped[list["Order"]] = relationship(back_populates="event", cascade="all, delete-orphan")


