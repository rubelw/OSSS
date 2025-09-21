
from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Boolean, DateTime, JSON, ForeignKey
from .common import Base, TimestampMixin

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


class FanPage(TimestampMixin, Base):
    __tablename__ = "fan_pages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_id: Mapped[str] = mapped_column(String, ForeignKey("schools.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String)
    content_md: Mapped[Optional[str]] = mapped_column(Text)
    published: Mapped[bool] = mapped_column(Boolean, default=False)

class FanAppSetting(Base):
    __tablename__ = "fan_app_settings"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_id: Mapped[str] = mapped_column(String, ForeignKey("schools.id"), unique=True, nullable=False)
    theme: Mapped[Optional[dict]] = mapped_column(JSON)
    features: Mapped[Optional[dict]] = mapped_column(JSON)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
