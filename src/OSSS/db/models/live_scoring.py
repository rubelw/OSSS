# src/OSSS/db/models/live_scoring.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from OSSS.db.base import Base, UUIDMixin, GUID
from OSSS.db.models.common_enums import LiveStatus  # ← fix import


class LiveScoring(UUIDMixin, Base):
    __tablename__ = "live_scoring"

    # Columns
    game_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    status: Mapped[LiveStatus] = mapped_column(
        Enum(LiveStatus, name="live_status", native_enum=False),
        default=LiveStatus.live,
        nullable=False
    )
    feed_url: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True)

    # Relationships
    game: Mapped["Game"] = relationship(
        "Game", back_populates="live_scoring_sessions"
    )
