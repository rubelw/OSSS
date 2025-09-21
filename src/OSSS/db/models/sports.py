# src/OSSS/db/models/sports.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, UUIDMixin, GUID
from .school import School

class Sport(UUIDMixin, Base):
    __tablename__ = "sports"
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)

    teams: Mapped[list["Team"]] = relationship("Team", back_populates="sport", cascade="all, delete-orphan")

class Season(UUIDMixin, Base):
    __tablename__ = "seasons"
    name: Mapped[str] = mapped_column(sa.String(64), nullable=False)  # e.g. "2025-2026"
    start_year: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    end_year: Mapped[int] = mapped_column(sa.Integer, nullable=False)

class Team(UUIDMixin, Base):
    __tablename__ = "teams"

    school_id: Mapped[str] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    sport_id: Mapped[str]  = mapped_column(GUID(), ForeignKey("sports.id",  ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)

    school: Mapped[School] = relationship("School", back_populates="teams")
    sport:  Mapped[Sport]  = relationship("Sport",  back_populates="teams")
