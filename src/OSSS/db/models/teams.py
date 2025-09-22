"""
SQLAlchemy model for Team with managed metadata.
Updated with __allow_managed__, NOTE (ClassVar[str]), and __table_args__.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import ClassVar

from sqlalchemy import Column, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Team(UUIDMixin, Base):
    __tablename__ = "teams"
    __allow_unmapped__ = True  # SQLAlchemy 2.x compatibility
    __allow_managed__ = True

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores team records for the application. "
        "Key attributes include name and mascot. "
        "References related entities via: sport, season. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores team records for the application. "
            "Key attributes include name and mascot. "
            "References related entities via: sport, season. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores team records for the application. "
                "Key attributes include name and mascot. "
                "References related entities via: sport, season. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "2 foreign key field(s) detected."
            ),
        },
    }

    sport_id = Column(GUID(), ForeignKey("sports.id"), nullable=False)
    name = Column(String(255), nullable=False)
    mascot = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("now()"), onupdate=datetime.utcnow, nullable=False)

    sport = relationship("Sport", back_populates="teams")

    season: Mapped["Season"] = relationship("Season", back_populates="teams")
    season_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seasons.id"), index=True)

    # backref to messages
    messages: Mapped[list["TeamMessage"]] = relationship(
        "TeamMessage",
        back_populates="team",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    score_entries = relationship("ScoreEntry", back_populates="team")
    games = relationship("Game", back_populates="team")

    school_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("schools.id"), nullable=False, index=True
    )
    school: Mapped["School"] = relationship("School", back_populates="teams")
