# src/OSSS/db/models/score_entry.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB


class ScoreEntry(UUIDMixin, Base):
    __tablename__ = "score_entries"

    game_id: Mapped[str] = mapped_column(GUID(), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    submitted_by: Mapped[str | None] = mapped_column(sa.String)  # user id
    submitted_at: Mapped[datetime | None] = mapped_column(sa.DateTime, default=datetime.utcnow)
    source: Mapped[str | None] = mapped_column(sa.String)  # manual, import, live
    notes: Mapped[str | None] = mapped_column(sa.Text)

    game: Mapped["Game"] = relationship("Game", back_populates="score_entries")