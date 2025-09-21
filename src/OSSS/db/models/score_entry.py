
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, DateTime, ForeignKey
from .common import Base
from .varsity_schedules import Game

class ScoreEntry(Base):
    __tablename__ = "score_entries"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, ForeignKey("games.id"), nullable=False)
    submitted_by: Mapped[Optional[str]] = mapped_column(String)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow)
    source: Mapped[Optional[str]] = mapped_column(String)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    game: Mapped[Game] = relationship(backref="score_entries")
