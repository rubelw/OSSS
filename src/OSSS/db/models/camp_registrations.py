"""
SQLAlchemy model for CampRegistration with managed metadata.
Updated with __allow_managed__, NOTE (ClassVar[str]), and __table_args__.
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB



class CampRegistration(UUIDMixin, Base):
    __tablename__ = "camp_registrations"
    __allow_unmapped__ = True  # SQLAlchemy 2.x compatibility
    __allow_managed__ = True

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores camp registrations records for the application. "
        "Key attributes include participant_name. "
        "References related entities via: camp, school. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores camp registrations records for the application. "
            "Key attributes include participant_name. "
            "References related entities via: camp, school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores camp registrations records for the application. "
                "Key attributes include participant_name. "
                "References related entities via: camp, school. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "2 foreign key field(s) detected."
            ),
        },
    }

    participant_name = Column(String(255), nullable=False)
    camp_id = Column(GUID(), ForeignKey("camps.id"), nullable=False)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("now()"), onupdate=datetime.utcnow, nullable=False)

    camp = relationship("Camp", back_populates="registrations")

    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))

    # ✅ name must match School.registrations
    school: Mapped["School"] = relationship(back_populates="camp_registrations")