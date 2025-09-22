# src/OSSS/db/models/games.py

from __future__ import annotations
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from ._helpers import ts_cols
from .common_enums import Level, LiveStatus


class Game(UUIDMixin, Base):
    __tablename__ = "games"

    season_id:    Mapped[str | None] = mapped_column(GUID(), ForeignKey("seasons.id", ondelete="SET NULL"), index=True)
    home_team_id: Mapped["GUID"] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), index=True,
                                                 nullable=False)
    away_team_id: Mapped["GUID"] = mapped_column(ForeignKey("teams.id", ondelete="RESTRICT"), index=True,
                                                 nullable=False)

    level:      Mapped[Level]      = mapped_column(Enum(Level, name="level", native_enum=False), nullable=False, default=Level.Varsity)
    status:     Mapped[LiveStatus] = mapped_column(Enum(LiveStatus, name="live_status", native_enum=False), nullable=False, default=LiveStatus.scheduled)
    starts_at:  Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    location:   Mapped[str | None]      = mapped_column(sa.String(255))
    home_score: Mapped[int | None]      = mapped_column(sa.Integer)
    away_score: Mapped[int | None]      = mapped_column(sa.Integer)

    created_at, updated_at = ts_cols()

    # NOTE: put the whole union inside one string to avoid the eval error
    season:    Mapped["Season | None"] = relationship("Season", backref="games")
    home_team: Mapped["Team"] = relationship(
        "Team",
        back_populates="games_home",
        foreign_keys=[home_team_id],
        lazy="joined",
    )

    away_team: Mapped["Team"] = relationship(
        "Team",
        back_populates="games_away",
        foreign_keys=[away_team_id],
        lazy="joined",
    )

    live_scoring_sessions: Mapped[list["LiveScoring"]] = relationship(
        "LiveScoring", back_populates="game", cascade="all, delete-orphan"
    )

    stat_imports: Mapped[list["StatImport"]] = relationship(
        "StatImport", back_populates="game", cascade="all, delete-orphan"
    )

    score_entries: Mapped[list["ScoreEntry"]] = relationship(
        "ScoreEntry", back_populates="game", cascade="all, delete-orphan"
    )

    manual_stats: Mapped[list["ManualStat"]] = relationship(
        "ManualStat", back_populates="game", cascade="all, delete-orphan"
    )