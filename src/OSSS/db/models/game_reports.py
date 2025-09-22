"""
SQLAlchemy model for GameReport with managed metadata.
Updated with __allow_managed__, NOTE (ClassVar[str]), and __table_args__.
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from sqlalchemy import Column, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class GameReport(UUIDMixin, Base):
    __tablename__ = "game_reports"
    __allow_unmapped__ = True  # SQLAlchemy 2.x compatibility
    __allow_managed__ = True

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores game report records for the application. "
        "Key attributes include report_type and content. "
        "References related entities via: game. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores game report records for the application. "
            "Key attributes include report_type and content. "
            "References related entities via: game. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores game report records for the application. "
                "Key attributes include report_type and content. "
                "References related entities via: game. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "1 foreign key field(s) detected."
            ),
        },
    }

    game_id = Column(GUID(), ForeignKey("games.id"), nullable=False)
    report_type = Column(String(100), nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("now()"), onupdate=datetime.utcnow, nullable=False)

    game = relationship("Game", back_populates="reports")
