"""
SQLAlchemy model for ScoreEntry with managed metadata.
Updated with __allow_managed__, NOTE (ClassVar[str]), and __table_args__.
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class ScoreEntry(UUIDMixin, Base):
    __tablename__ = "score_entries"
    __allow_unmapped__ = True  # SQLAlchemy 2.x compatibility
    __allow_managed__ = True

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores score entry records for the application. "
        "Key attributes include points and period. "
        "References related entities via: game, team. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores score entry records for the application. "
            "Key attributes include points and period. "
            "References related entities via: game, team. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores score entry records for the application. "
                "Key attributes include points and period. "
                "References related entities via: game, team. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "2 foreign key field(s) detected."
            ),
        },
    }

    team_id = Column(GUID(), ForeignKey("teams.id"), nullable=False)
    points = Column(Integer, nullable=False)
    period = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("now()"), onupdate=datetime.utcnow, nullable=False)

    team = relationship("Team", back_populates="score_entries")

    # FK type MUST match Game.id type
    game_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="score_entries",
    )
