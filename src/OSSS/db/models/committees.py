# committees.py
from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols


class Committee(UUIDMixin, Base):
    """
    Stores committee records for the application (CIC domain).
    Key attributes include name. References related entities via: organization, school.
    Includes standard audit timestamps (created_at, updated_at).
    """
    note: str = (
        "owner=board_of_education_governing_board; "
        "description=Stores cic committees records for the application. "
        "Key attributes include name. References related entities via: organization, school. "
        "Includes standard audit timestamps (created_at, updated_at). 8 column(s) defined. "
        "Primary key is `id`. 2 foreign key field(s) detected."
    )

    # IMPORTANT: use 'committees' to match FKs like ForeignKey('committees.id')
    __tablename__ = "committees"

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization_id: Mapped[Optional[Any]] = mapped_column(
        GUID(), ForeignKey("mentors.id", ondelete="SET NULL")
    )
    school_id = sa.Column(GUID(), ForeignKey("schools.id", ondelete="SET NULL"))
    name = sa.Column(sa.Text, nullable=False)
    description = sa.Column(sa.Text)
    status: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default=sa.text("'active'")
    )

    created_at, updated_at = ts_cols()

    __table_args__ = (
        sa.CheckConstraint(
            "(organization_id IS NOT NULL) OR (school_id IS NOT NULL)",
            name="ck_committee_scope",
        ),
        {
            "comment": (
                "Stores cic committees records for the application. Key attributes include name. "
                "References related entities via: organization, school. Includes standard audit "
                "timestamps (created_at, updated_at). 8 column(s) defined. Primary key is `id`. "
                "2 foreign key field(s) detected."
            )
        },
    )

    # Relationships
    memberships = relationship(
        "Membership",
        back_populates="committee",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    meetings = relationship(
        "Meeting",
        back_populates="committee",
        cascade="all, delete-orphan",
    )

    proposals = relationship(
        "Proposal",
        back_populates="committee",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
