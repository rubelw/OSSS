# src/OSSS/db/models/schools.py
from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Optional

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
