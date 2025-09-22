"""
SQLAlchemy model for LiveScoring with managed metadata.
Updated with __allow_managed__, NOTE (ClassVar[str]), and __table_args__.
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, String, Integer, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class LiveScoring(UUIDMixin, Base):
    __tablename__ = "live_scoring"
    __allow_unmapped__ = True  # SQLAlchemy 2.x compatibility
    __allow_managed__ = True

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores live scoring records for the application. "
        "Key attributes include score and status. "
        "References related entities via: game. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores live scoring records for the application. "
            "Key attributes include score and status. "
            "References related entities via: game. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores live scoring records for the application. "
                "Key attributes include score and status. "
                "References related entities via: game. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "1 foreign key field(s) detected."
            ),
        },
    }

    game_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("games.id"), nullable=False)
    score = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("now()"), onupdate=datetime.utcnow, nullable=False)

    # the string MUST be the Python class name of your Game model
    game: Mapped["Game"] = relationship(back_populates="live_scoring")