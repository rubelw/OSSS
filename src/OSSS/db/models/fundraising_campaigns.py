"""
SQLAlchemy model for FundraisingCampaign with managed metadata.
Updated with __allow_managed__, NOTE (ClassVar[str]), and __table_args__.
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar, List

from sqlalchemy import Column, DateTime, ForeignKey, String, Integer, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB


class FundraisingCampaign(UUIDMixin, Base):
    __tablename__ = "fundraising_campaigns"
    __allow_unmapped__ = True  # SQLAlchemy 2.x compatibility
    __allow_managed__ = True

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores fundraising campaigns records for the application. "
        "Key attributes include title and goal amount. "
        "References related entities via: school. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores fundraising campaigns records for the application. "
            "Key attributes include title and goal amount. "
            "References related entities via: school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores fundraising campaigns records for the application. "
                "Key attributes include title and goal amount. "
                "References related entities via: school. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "1 foreign key field(s) detected."
            ),
        },
    }

    title = Column(String(255), nullable=False)
    goal_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("now()"), onupdate=datetime.utcnow, nullable=False)

    donations: Mapped[List["Donation"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan"
    )

    # Make sure the FK matches your School PK & tablename
    school_id: Mapped[GUID] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    school: Mapped["School"] = relationship(
        "School",
        back_populates="fundraising_campaigns",
    )
