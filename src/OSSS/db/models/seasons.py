"""
SQLAlchemy model for Season with managed metadata.
Updated with __allow_managed__, NOTE (ClassVar[str]), and __table_args__.
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from sqlalchemy import Column, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship, Mapped
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Season(UUIDMixin, Base):
    __tablename__ = "seasons"
    __allow_unmapped__ = True  # SQLAlchemy 2.x compatibility
    __allow_managed__ = True

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores season records for the application. "
        "Key attributes include name and year. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "0 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores season records for the application. "
            "Key attributes include name and year. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "0 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores season records for the application. "
                "Key attributes include name and year. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "0 foreign key field(s) detected."
            ),
        },
    }

    name = Column(String(255), nullable=False)
    year = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("now()"), onupdate=datetime.utcnow, nullable=False)

    # inverse side must match back_populates
    games: Mapped[list["Game"]] = relationship(
        "Game", back_populates="season", cascade="all, delete-orphan"
    )

    teams: Mapped[list["Team"]] = relationship("Team", back_populates="season", cascade="all, delete-orphan")
