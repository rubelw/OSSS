"""
SQLAlchemy model for Camp with managed metadata.
Updated with __allow_managed__, NOTE (ClassVar[str]), and __table_args__.
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship, mapped_column, Mapped
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB



class Camp(UUIDMixin, Base):
    __tablename__ = "camps"
    __allow_unmapped__ = True  # SQLAlchemy 2.x compatibility
    __allow_managed__ = True

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores camps records for the application. "
        "Key attributes include name. "
        "References related entities via: school. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores camps records for the application. "
            "Key attributes include name. "
            "References related entities via: school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores camps records for the application. "
                "Key attributes include name. "
                "References related entities via: school. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "1 foreign key field(s) detected."
            ),
        },
    }

    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("now()"), onupdate=datetime.utcnow, nullable=False)

    registrations = relationship("CampRegistration", back_populates="camp")

    school_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("schools.id"), nullable=False
    )
    school: Mapped["School"] = relationship(
        "School", back_populates="camps"
    )
