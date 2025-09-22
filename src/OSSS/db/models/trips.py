"""
SQLAlchemy model for Trip with managed metadata.
Updated with __allow_managed__, NOTE (ClassVar[str]), and __table_args__.
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from sqlalchemy import Column, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Trip(UUIDMixin, Base):
    __tablename__ = "trips"
    __allow_unmapped__ = True  # SQLAlchemy 2.x compatibility
    __allow_managed__ = True

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores trip records for the application. "
        "Key attributes include destination and purpose. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "0 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores trip records for the application. "
            "Key attributes include destination and purpose. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "0 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores trip records for the application. "
                "Key attributes include destination and purpose. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "0 foreign key field(s) detected."
            ),
        },
    }

    destination = Column(String(255), nullable=False)
    purpose = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("now()"), onupdate=datetime.utcnow, nullable=False)
