# src/OSSS/db/models/manual_stats.py
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB


class ManualStat(UUIDMixin, Base):
    __tablename__ = "manual_stats"

    game_id: Mapped[str] = mapped_column(GUID(), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id: Mapped[str] = mapped_column(GUID(), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    athlete_id: Mapped[str | None] = mapped_column(sa.String)  # optional athletes table
    payload: Mapped[dict] = mapped_column(JSONB(), nullable=False, default=dict)  # arbitrary per-sport stats
    created_at: Mapped[datetime] = mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)

    game: Mapped["Game"] = relationship("Game", back_populates="manual_stats")
    team: Mapped["Team"] = relationship("Team")
