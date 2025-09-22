# src/OSSS/db/models/game_reports.py
from __future__ import annotations

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB


class GameReport(UUIDMixin, Base):
    __tablename__ = "game_reports"

    game_id:      Mapped[str]             = mapped_column(GUID(), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    report:       Mapped[dict | None]     = mapped_column(JSONB())  # box score, summaries
    generated_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True), default=datetime.utcnow)

    # relationships
    game: Mapped["Game"] = relationship("Game", backref="reports")
