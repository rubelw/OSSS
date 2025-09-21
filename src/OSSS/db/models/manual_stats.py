
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, JSON, DateTime, ForeignKey
from .common import Base
from .varsity_schedules import Game

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


class ManualStat(Base):
    __tablename__ = "manual_stats"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    game_id: Mapped[str] = mapped_column(String, ForeignKey("games.id"), nullable=False)
    team_id: Mapped[str] = mapped_column(String, ForeignKey("teams.id"), nullable=False)
    athlete_id: Mapped[Optional[str]] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    game: Mapped[Game] = relationship(backref="manual_stats")
