# src/OSSS/db/models/events.py
from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class Event(UUIDMixin, Base):
    __tablename__ = "events"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] = (
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
        "comment": (
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
            "description": (
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

    # --- foreign keys ---------------------------------------------------------
    school_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    activity_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("activities.id", ondelete="SET NULL")
    )

    # --- fields ---------------------------------------------------------------
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(sa.Text)
    starts_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    venue: Mapped[str | None] = mapped_column(sa.String(255))
    status: Mapped[str] = mapped_column(
        sa.String(16), server_default=text("'draft'"), nullable=False
    )  # draft|published|cancelled
    attributes: Mapped[dict | None] = mapped_column(JSONB())

    # --- timestamps -----------------------------------------------------------
    created_at, updated_at = ts_cols()

    # --- relationships (string targets avoid import cycles) -------------------
    # relationships (use string refs to avoid import cycles)
    activity: Mapped[Optional["Activity"]] = relationship(
        "Activity", back_populates="events"
    )

    school: Mapped["School"] = relationship(
        "School", back_populates="events"
    )

    ticket_types: Mapped[list["TicketType"]] = relationship(
        "TicketType",
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="event",
        cascade="all, delete-orphan",
    )

    assignments: Mapped[list["WorkAssignment"]] = relationship("WorkAssignment", back_populates="event")
