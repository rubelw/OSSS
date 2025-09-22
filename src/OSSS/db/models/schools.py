# src/OSSS/db/models/schools.py
from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB


class School(UUIDMixin, Base):
    __tablename__ = "schools"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] = (
        "owner=division_of_technology_data; "
        "description=Stores schools records for the application. "
        "Key attributes include name. "
        "References related entities via: nces school, organization. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "10 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores schools records for the application. "
            "Key attributes include name. "
            "References related entities via: nces school, organization. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores schools records for the application. "
                "Key attributes include name. "
                "References related entities via: nces school, organization. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "10 column(s) defined. "
                "Primary key is `id`. "
                "2 foreign key field(s) detected."
            ),
        },
    }

    # --- columns --------------------------------------------------------------
    organization_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # changed to String(255) + index=True per your integration request
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)

    school_code: Mapped[Optional[str]] = mapped_column(sa.Text, unique=True)
    nces_school_id: Mapped[Optional[str]] = mapped_column(sa.Text)
    building_code: Mapped[Optional[str]] = mapped_column(sa.Text)
    type: Mapped[Optional[str]] = mapped_column(sa.Text)
    timezone: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )

    # --- relationships --------------------------------------------------------
    # Use string targets to avoid circular imports.
    teams: Mapped[list["Team"]] = relationship(
        "Team",
        back_populates="school",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["Event"]] = relationship(
        "Event",
        back_populates="school",
        cascade="all, delete-orphan",
    )

    # class name must be exactly "School"
    fan_app_settings: Mapped[list["FanAppSetting"]] = relationship(
        back_populates="school",
        cascade="all, delete-orphan",
    )

    # Reverse side for FanPage.school
    fan_pages: Mapped[List["FanPage"]] = relationship(
        "FanPage",
        back_populates="school",
        cascade="all, delete-orphan",
        lazy="selectin",  # optional, matches your pattern on other collections
    )

    camps: Mapped[list["Camp"]] = relationship(
        "Camp", back_populates="school", cascade="all, delete-orphan"
    )

    # one-to-many: a school has many teams
    teams: Mapped[list["Team"]] = relationship(
        "Team", back_populates="school", cascade="all, delete-orphan"
    )

    donations: Mapped[list["Donation"]] = relationship(
        "Donation",
        back_populates="school",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    app_settings: Mapped[list["FanAppSetting"]] = relationship(
        "FanAppSetting", back_populates="school", cascade="all, delete-orphan"
    )

    concession_sales = relationship(
        "ConcessionSale",
        primaryjoin="School.id == foreign(ConcessionSale.school_id)",
        viewonly=True,  # consider viewonly if you don't want writes
    )

    concession_items: Mapped[list["ConcessionItem"]] = relationship(
        "ConcessionItem",
        back_populates="school",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # ✅ define the reverse side that Registration.back_populates points to
    camp_registrations: Mapped[list["CampRegistration"]] = relationship(
        back_populates="school",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Fundraising: one School -> many FundraisingCampaigns
    fundraising_campaigns: Mapped[list["FundraisingCampaign"]] = relationship(
        "FundraisingCampaign",
        back_populates="school",
        cascade="all, delete-orphan",
    )