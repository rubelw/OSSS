# src/OSSS/db/models/game_programs.py
from __future__ import annotations

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID


class GameProgram(UUIDMixin, Base):
    __tablename__ = "game_programs"

    game_id:      Mapped[str]              = mapped_column(GUID(), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    program_uri:  Mapped[str | None]       = mapped_column(sa.String(255))  # generated PDF path/URL
    generated_at: Mapped[datetime | None]  = mapped_column(sa.TIMESTAMP(timezone=True), default=datetime.utcnow)

    # relationships
    game: Mapped["Game"] = relationship("Game", backref="programs")
