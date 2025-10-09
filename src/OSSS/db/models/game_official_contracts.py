"""
SQLAlchemy model for GameOfficialContract with managed metadata.
Updated with __allow_managed__, NOTE (ClassVar[str]), and __table_args__.
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from sqlalchemy import Column, DateTime, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class GameOfficialContract(UUIDMixin, Base):
    __tablename__ = "game_official_contracts"
    __allow_unmapped__ = True  # SQLAlchemy 2.x compatibility
    __allow_managed__ = True

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores game official contracts records for the application. "
        "Key attributes include fee_cents. "
        "References related entities via: game, official. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores game official contracts records for the application. "
            "Key attributes include fee_cents. "
            "References related entities via: game, official. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores game official contracts records for the application. "
                "Key attributes include fee_cents. "
                "References related entities via: game, official. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "2 foreign key field(s) detected."
            ),
        },
    }

    game_id = Column(GUID(), ForeignKey("games.id"), nullable=False)
    official_id = Column(GUID(), ForeignKey("officials.id"), nullable=False)
    fee_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("now()"), onupdate=datetime.utcnow, nullable=False)

    game = relationship("Game", back_populates="official_contracts")
    official = relationship("Official", back_populates="contracts")
