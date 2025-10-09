"""
SQLAlchemy model for Donation with managed metadata.
Updated with __allow_managed__, NOTE (ClassVar[str]), and __table_args__.
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Donation(UUIDMixin, Base):
    __tablename__ = "donations"
    __allow_unmapped__ = True  # SQLAlchemy 2.x compatibility
    __allow_managed__ = True

    NOTE: ClassVar[str] = (
        "owner=athletics_activities_enrichment | division_of_schools; "
        "description=Stores donations records for the application. "
        "Key attributes include donor_name and amount. "
        "References related entities via: school. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores donations records for the application. "
            "Key attributes include donor_name and amount. "
            "References related entities via: school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores donations records for the application. "
                "Key attributes include donor_name and amount. "
                "References related entities via: school. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "1 foreign key field(s) detected."
            ),
        },
    }

    donor_name = Column(String(255), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=text("now()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("now()"), onupdate=datetime.utcnow, nullable=False)

    school_id: Mapped[str] = mapped_column(
        ForeignKey("schools.id"), nullable=False, index=True
    )

    school: Mapped["School"] = relationship(
        "School",
        back_populates="donations",
        lazy="joined",
    )

    # inside class Donation(UUIDMixin, Base):
    # replace the current int-typed FK with a GUID/UUID to match FundraisingCampaign.id
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        GUID,  # <-- crucial: use the same type your UUIDMixin uses
        ForeignKey("fundraising_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    campaign: Mapped["FundraisingCampaign"] = relationship(
        "FundraisingCampaign",
        back_populates="donations",
    )