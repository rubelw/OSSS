"""
SQLAlchemy model for Game with managed metadata.
Updated with __allow_managed__, NOTE (ClassVar[str]), and __table_args__.
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar, TYPE_CHECKING
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, String, Integer, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

if TYPE_CHECKING:
    from .seasons import Season  # typing only

class Game(UUIDMixin, Base):
    __tablename__ = "games"
    __allow_unmapped__ = True  # SQLAlchemy 2.x compatibility
    __allow_managed__ = True

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores games records for the application. "
        "Key attributes include opponent and score. "
        "References related entities via: season, team. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores games records for the application. "
            "Key attributes include opponent and score. "
            "References related entities via: season, team. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores games records for the application. "
                "Key attributes include opponent and score. "
                "References related entities via: season, team. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "2 foreign key field(s) detected."
            ),
        },
    }

    team_id = Column(GUID(), ForeignKey("teams.id"), nullable=False)
    opponent = Column(String(255), nullable=False)
    score = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("now()"), onupdate=datetime.utcnow, nullable=False)

    team = relationship("Team", back_populates="games")
    reports = relationship("GameReport", back_populates="game")
    programs = relationship("GameProgram", back_populates="game")
    official_contracts = relationship("GameOfficialContract", back_populates="game")

    manual_stats: Mapped[list[ManualStat]] = relationship(back_populates="game")

    # one-to-one? use uselist=False
    live_scoring: Mapped["LiveScoring"] = relationship(
        back_populates="game",
        cascade="all, delete-orphan",
        uselist=False,  # drop this if it’s one-to-many
    )

    season_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("seasons.id"), nullable=False, index=True
    )

    # use a string target to avoid import-order issues
    season: Mapped["Season"] = relationship(
        "Season", back_populates="games"
    )

    # This attribute name MUST match the other side's back_populates
    score_entries: Mapped[list["ScoreEntry"]] = relationship(
        "ScoreEntry",
        back_populates="game",
        cascade="all, delete-orphan",
        passive_deletes=True,  # optional, pairs nicely with ondelete="CASCADE"
    )