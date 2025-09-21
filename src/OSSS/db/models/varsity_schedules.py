
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Enum, ForeignKey
from .common import Base, TimestampMixin, Level, LiveStatus

from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey

class School(Base):
    __tablename__ = "schools"
    id: Mapped[str] = mapped_column(String, primary_key=True)

class Sport(Base):
    __tablename__ = "sports"
    id: Mapped[str] = mapped_column(String, primary_key=True)

class Team(Base):
    __tablename__ = "teams"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_id: Mapped[str] = mapped_column(String, ForeignKey("schools.id"))
    sport_id: Mapped[str] = mapped_column(String, ForeignKey("sports.id"))

class Season(Base):
    __tablename__ = "seasons"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_id: Mapped[str] = mapped_column(String, ForeignKey("schools.id"))

class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_id: Mapped[str] = mapped_column(String, ForeignKey("schools.id"))
    team_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("teams.id"), nullable=True)


class Game(TimestampMixin, Base):
    __tablename__ = "games"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    season_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("seasons.id"))
    home_team_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("teams.id"))
    away_team_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("teams.id"))
    level: Mapped[Level] = mapped_column(Enum(Level, name="level", native_enum=False))
    status: Mapped[LiveStatus] = mapped_column(Enum(LiveStatus, name="live_status", native_enum=False), default=LiveStatus.scheduled)
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    location: Mapped[Optional[str]] = mapped_column(String)
    home_score: Mapped[Optional[int]] = mapped_column(Integer)
    away_score: Mapped[Optional[int]] = mapped_column(Integer)

    home_team: Mapped[Optional[Team]] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped[Optional[Team]] = relationship(foreign_keys=[away_team_id])
    season: Mapped[Optional[Season]] = relationship()
